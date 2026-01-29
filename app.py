import streamlit as st
import pandas as pd
import requests
import threading
import sys
import subprocess
import time

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

    [안티그라비티 행동 강령]
    1. **무중력 요약 (Zero-Gravity Summary):** 핵심만 둥둥 띄워 보여주듯 명료하게 요약하십시오.
    2. **부담 없는 톤 (Uplifting Tone):** 스마트하고 세련되며 긍정적인 에너지를 전달하십시오.
    3. **확실한 착륙 (Safe Landing):** 모르는 내용은 솔직히 말하고 대안을 제시하십시오.
    4. **즉시 계산 (Calculator Mode):** 사용자가 숫자(소득, 재산 등)를 말하면 공식을 설명하기보다 **직접 계산해서 결과값**을 알려주십시오.
    5. **시각화 및 링크 연결:** - 이미지: `![설명](URL)` 
       - 링크: `� [제목(클릭)](URL)`

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
            
            # 화면에 출력
            st.write(answer)
            
            # 대화 내역에 저장
            st.session_state.messages.append({"role": "assistant", "content": answer, "avatar": "💎"})
