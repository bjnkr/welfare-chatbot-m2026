import streamlit as st
import pandas as pd
import requests
import threading
import sys
import subprocess
import time
import re

# --------------------------------------------------------------------------
# 1. [필수] 라이브러리 강제 업데이트 (서버야 정신차려!)
# --------------------------------------------------------------------------
# 이 코드가 있어야 최신 모델(1.5, 2.0) 이름을 인식할 수 있습니다.
try:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "google-generativeai"])
    import google.generativeai as genai
except Exception as e:
    pass

# --------------------------------------------------------------------------
# 2. 기본 설정
# --------------------------------------------------------------------------
st.set_page_config(page_title="복지 챗봇 AI", page_icon="💎")

st.markdown("""
<style>
#MainMenu {visibility: hidden;}
header {visibility: hidden;}
footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --------------------------------------------------------------------------
# 3. 데이터 로드
# --------------------------------------------------------------------------
knowledge_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vT3EmDQ002d2Y8dQkgHE4A_wSErUfgK9xU0QJ8pz0yu_W0F7Q9VN1Es-_OKKJjBobIpZr8tBP3aJQ3-/pub?output=csv"
example_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSyjxNdN93yLxvN_FtOHJb28_V_olidRIJsRUbja75zBwN4TUE1gLThDt79EiVJp9PhE7kJ4qJASymi/pub?output=csv"

@st.cache_data
def load_data_v2():  # <--- 이름 변경 (v2)
    # 1. 지식 데이터 로드
    df_knowledge = pd.read_csv(knowledge_url)
    
    # 2. 학습 예시 데이터 로드
    try:
        df_examples = pd.read_csv(example_url)
        example_text = ""
        for _, row in df_examples.iterrows():
            if pd.notna(row[0]) and pd.notna(row[1]):
                example_text += f"사용자: {row[0]}\nAI: {row[1]}\n\n"
    except:
        example_text = "예시 데이터를 불러오는 데 실패했습니다."
        
    return df_knowledge, example_text

# 3. 데이터 불러오기 실행 (여기도 v2로 변경!)
df, few_shot_examples = load_data_v2()

# 4. 에러 체크
if df.empty:
    st.error("데이터를 불러오지 못했습니다.")
    
# --------------------------------------------------------------------------
# 4. 로그 전송
# --------------------------------------------------------------------------
def log_to_google_form(question, answer, status):
    def send_request():
        form_url = "https://docs.google.com/forms/d/e/1FAIpQLSfKO_6h_Zge_6__lUhAdEFSZ0tsGXe_6BiMNc3_uJqjsYT-Kw/formResponse"
        data = {
            "entry.878148217": question,
            "entry.1467732690": answer,
            "entry.1569618620": status
        }
        try:
            requests.post(form_url, data=data)
        except:
            pass
    thread = threading.Thread(target=send_request)
    thread.start()

# --------------------------------------------------------------------------
# 5. [핵심] 모델 자동 선택 (2.0 -> 1.5 -> Pro)
# --------------------------------------------------------------------------
def get_generative_model():
    # 모델 후보군 (우선순위 순서대로)
    # 2.0 Flash -> 1.5 Flash -> Latest Flash -> Pro (Legacy)
    candidates = [
        ("gemini-2.0-flash", "Gemini 2.0 Flash"),
        ("gemini-2.0-flash-exp", "Gemini 2.0 Flash (Exp)"),
        ("gemini-1.5-flash", "Gemini 1.5 Flash"),
        ("gemini-flash-latest", "Gemini Flash (Latest)"), 
        ("gemini-pro", "Gemini Pro (Legacy)")
    ]

    for model_id, name in candidates:
        try:
            model = genai.GenerativeModel(model_id)
            # 가벼운 테스트 요청으로 실제 작동 여부 확인
            model.generate_content("test")
            return model, name
        except Exception:
            continue
            
    return None, "Error"

# --------------------------------------------------------------------------
# 5-1. [검증] 거짓말 탐지 필터 (Hallucination Filter)
# --------------------------------------------------------------------------
def filter_hallucinations(text, context):
    """
    AI가 생성한 텍스트(text) 안에 있는 링크가
    실제 참고자료(context)에 없는 가짜라면, 
    링크만 쏙 빼고 텍스트만 남깁니다.
    """
    # 1. 이미지 링크 찾기 (![설명](주소))
    img_pattern = r'!\[.*?\]\((.*?)\)'
    
    # 2. 일반 링크 찾기 ([설명](주소))
    link_pattern = r'\[.*?\]\((.*?)\)'
    
    # 3. 모든 링크(URL) 추출
    found_urls = re.findall(img_pattern, text) + re.findall(link_pattern, text)
    
    for url in found_urls:
        # 4. 만약 URL이 참고자료(context_data)에 없다면?
        if url not in context:
            # 해당 URL이 포함된 마크다운 태그를 통째로 삭제
            # 예: ![이상한사진](http://fake.com) -> "" (빈칸)
            text = text.replace(f"({url})", "") # 주소 부분만 지움 (설명 텍스트는 남김)
            
    return text

# --------------------------------------------------------------------------
# 6. 메인 로직
# --------------------------------------------------------------------------
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("API 키가 설정되지 않았습니다.")
    st.stop()

df, few_shot_examples = load_data_v2()

# 모델 로드 시도
model, model_name = get_generative_model()



st.image("https://bjn.kr/img_bjn/logo2.png", width=70)

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "안녕하세요. 무엇을 도와드릴까요?", "avatar": "💎"}]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar=msg.get("avatar")):
        st.write(msg["content"])

if prompt := st.chat_input("질문을 입력하세요"):
    st.session_state.messages.append({"role": "user", "content": prompt, "avatar": "😎"})
    with st.chat_message("user", avatar="😎"):
        st.write(prompt)

    # Context data (Assistant added to ensure availability)
    context_data = df.to_csv(index=False)

    # 1. [기억 로직] 이전 대화 내용 정리 (방금 질문은 제외)
    conversation_history = ""
    for msg in st.session_state.messages[:-1]:
        role = "사용자" if msg['role'] == "user" else "AI"
        conversation_history += f"{role}: {msg['content']}\n"

    # 2. [프롬프트 조립]
    system_prompt = f"""
    당신은 복지 정보의 복잡한 중력을 거스르는 AI 어시스턴트, **'복지N'**입니다.
    당신의 미션은 삶의 무게와 행정 절차의 복잡함에 지친 사용자에게 **'가벼움(Easy)'**과 **'상승(Up)'**의 경험을 제공하는 것입니다.

    [소득인정액 정밀 계산 로직 (2026년 기준)]
                사용자가 소득/재산 정보를 주면 아래 4단계 로직을 엄수하여 계산하시오.

                **0. 기준 중위소득 및 상수 (Reference):**
                   - 1인: 2,564,238원 | 2인: 4,199,292원 | 3인: 5,359,036원 | 4인: 6,494,738원
                   - 재산 공제액(기본재산액): 서울(9,900만), 경기(8,000만), 광역/세종/창원(7,700만), 그 외(5,300만)
                   - 주거용 재산 한도: 서울(1.72억), 경기(1.51억), 광역(1.46억), 그 외(1.12억)

                **1. 소득 평가액 (Income Evaluation):**
                   - **근로소득:** (월 소득 - *인적 공제*) × 70%
                     * *인적 공제(선공제) - 중복 적용 불가, 아래 조건 중 하나만 적용 , 두가지 이상 해당 괼 경우 많은 금액 적용:*
                       - **대학생:** 60만 원
                       - **34세 이하 청년 (예: 20세~34세):** 60만 원
                       - **65세 이상 또는 장애인:** 20만 원
                       - **그 외 일반 (35세~64세, 비장애인):** 0원
                     * *중요: 31세는 "34세 이하"에 해당하므로 60만 원 공제 적용*
                   - **사업소득:** 월 소득 × 70%
                   - **국민연금:** 납부액의 75%를 소득에서 차감
                   - **사적 이전소득:** (월 지원금 - 중위소득의 15%) ※ 15% 미만은 0원 처리

                **2. 재산의 소득 환산액 (정밀 순차 차감 로직):**
                   - 사용자가 제시한 로직을 엄격히 준수하여 아래 순서대로 계산하시오.

                   **[Step 1] 재산의 평가 및 분류:**
                     1. **주거용 재산:** 자가(공시지가), 전/월세 보증금(95%만 인정).
                     2. **주거용 재산 한도 체크:**
                        - 지역별 한도: 서울(1.72억), 경기(1.51억), 광역/세종/창원(1.46억), 그 외(1.12억).
                        - **초과분 이관:** (평가액 - 한도)가 양수라면, 그 초과 금액은 **'일반 재산'**으로 합산한다.
                        - 한도 내 금액만 **'주거용 재산'**으로 남긴다.
                     3. **일반 재산:** 기존 일반재산 + (주거용 한도 초과분) + (승용차 가액).
                     4. **금융 재산:** 총 금융재산.

                   **[Step 2] 공제 가능 총액 설정:**
                     - **총 공제액(Pool)** = (기본재산공제액 + 부채)
                     - *기본재산공제액:* 서울(9,900만), 경기(8,000만), 광역/세종/창원(7,700만), 그 외(5,300만).

                   **[Step 3] 기본재산 금액 , 부채 차감:**
                     1. **주거용 재산 차감:**
                        - (주거용 재산 - 총 공제액)
                        - 남은 금액(양수) × **1.04% (연)** ÷ 12 = A (월 환산액)
                        - *중요: 1.04%는 연 환산율이므로 반드시 12로 나누어 월 환산액을 구할 것*
                        - 만약 공제액이 남았다면 **다음 단계로 이월 금액.**
                     2. **일반 재산 차감:**
                        - (일반 재산 - 이월된 공제액)
                        - 이월 공제금액이 없다면 일반 재산 × **4.17% (연)** ÷ 12 = B (월 환산액)
                        - 남은 금액(양수) × **4.17% (연)** ÷ 12 = B (월 환산액)
                        - *중요: 4.17%는 연 환산율이므로 반드시 12로 나누어 월 환산액을 구할 것*
                        - 만약 공제액이 여전히 남았다면 **다음 단계로 이월.**
                     3. **금융 재산 차감 (순서 엄수):**
                        - **1차 차감 (기본공제):** (금융 재산 - Step 2에서 넘어온 남은 이월 공제액)
                        - **2차 차감 (생활준비금):** 위 1차 차감 후 남은 금액에서 **500만 원**을 추가로 차감.
                        - **최종 환산:** 2차 차감 후에도 남은 금액(양수) × **6.26% (연)** ÷ 12 = C (월 환산액)
                        - *중요: 6.26%는 연 환산율이므로 반드시 12로 나누어 월 환산액을 구할 것*

                   **[Step 4] 최종 합산:**
                     - 재산 소득 환산액 = A + B + C

                **3. 최종 계산식:**
                   - 소득인정액 = (1. 소득 평가액) + (2. 재산의 소득 환산액)

                **4. 답변 가이드:**
                   - 계산 과정은 암산하지 말고 단계별로 보여줄 것.
                   - 특히 **'자동차'**가 있다면 배기량과 연식을 물어보고, 100% 환산율 적용 대상인지 경고할 것.

                **5. 계산 결과 출력 형식 (필수):**
                   소득인정액을 계산할 때는 반드시 아래 형식으로 **계층적 구조**를 사용하여 출력하십시오.
                   
                   ```
                   ## 재산의 소득 환산액: [총액] 원
                   
                   ### 주거용 재산: [환산액] 원
                   (계산식 표시)
                   - 재산 가액: [금액] 원
                   - 월세/전세 적용 (95%): [금액] 원
                   - 지역별 한도액 적용: [금액] 원
                   - 한도 초과분 → 일반재산 이관: [금액] 원
                   - 기본재산/부채 공제: (-) [금액] 원
                   
                   ### 일반 재산: [환산액] 원
                   (계산식 표시)
                   - 재산 가액: [금액] 원
                   - 주거재산 한도 초과분 합산: [금액] 원
                   - 기본재산/부채 공제: (-) [금액] 원
                   
                   ### 금융 재산: [환산액] 원
                   (계산식 표시)
                   - 재산 가액: [금액] 원
                   - 금융재산 공제 (500만원): (-) [금액] 원
                   - 기본재산/부채 공제: (-) [금액] 원
                   ```
                   
                   - **들여쓰기**를 사용하여 상위-하위 관계를 명확히 표시할 것
                   - 각 재산 유형별로 **섹션을 구분**하여 가독성을 높일 것
                   - 금액은 **천 단위 구분 쉼표** 사용 (예: 1,000,000 원)
                   - 공제 항목은 **(-) 기호**로 명확히 표시할 것

    [행동 강령]
    1. **무중력 요약 (Zero-Gravity Summary):** 핵심만 둥둥 띄워 보여주듯 명료하게 요약하십시오.
    2. **부담 없는 톤 (Uplifting Tone):** 스마트하고 세련되며 긍정적인 에너지를 전달하십시오.
    3. **확실한 착륙 (Safe Landing):** 모르는 내용은 솔직히 말하고 대안을 제시하십시오.
    4. **즉시 계산 (Calculator Mode):** 사용자가 숫자(소득, 재산 등)를 말하면 공식을 설명하기보다 **직접 계산해서 결과값**을 알려주십시오.
    5. **시각화 및 링크 연결 (엄격 모드):**
                   - **절대 원칙:** 반드시 제공된 [참고 자료]에 **실제로 존재하는 URL만** 사용하십시오. 
                   - AI가 임의로 인터넷에서 URL을 가져오거나 생성하는 것을 **엄격히 금지**합니다.
                   - 자료에 이미지/링크가 없다면, 억지로 만들지 말것.
                   - **이미지:** `![이미지](URL)`
                   - **링크:** `🔗 [제목](URL)`
    6. **자동차 필터링:** 사용자가 자동차가 있다고 하면, 반드시 "배기량(cc), 연식, 차종, 장애인 여부"를 먼저 확인하시오.
    7. **100% 환산 경고:** 일반 승용차(2000cc 이상, 10년 미만 등)인 경우, "차량가액이 월 소득으로 100% 잡혀 수급이 어렵습니다"라고 명확히 경고하시오.

    [답변 스타일 예시]
    {few_shot_examples}

    [이전 대화 내역]
    {conversation_history}

    [참고 자료]
    {context_data}

    [사용자 질문]
    {prompt}
    """

    # 3. [답변 생성 및 출력]
    with st.chat_message("assistant"):
        with st.spinner("분석 중입니다... 🚀"):
            # AI에게 질문 던지기
            response = model.generate_content(system_prompt)
            answer = response.text
            
            # ▼▼▼ [거짓말 탐지기 적용] ▼▼▼
            # 답변을 화면에 뿌리기 전에 필터링!
            answer = filter_hallucinations(answer, context_data)
            # ▲▲▲ [적용 완료] ▲▲▲         

            
            # 화면에 출력
            st.write(answer)
            
            # 대화 내역에 저장
            st.session_state.messages.append({"role": "assistant", "content": answer, "avatar": "💎"})
