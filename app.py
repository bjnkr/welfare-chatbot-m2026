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

    with st.chat_message("assistant", avatar="💎"):
        message_placeholder = st.empty()
        
        if df.empty:
            message_placeholder.error("데이터 로드 실패")
            st.stop()
        
        if not model:
            message_placeholder.error("AI 모델을 불러오지 못했습니다.")
            st.stop()

        with st.spinner(f"{model_name}가 답변 중입니다... 💬"):
            try:
                context_data = df.to_csv(index=False)
                
                system_prompt = f"""
                너는 '대한민국 최고의 복지 상담사'야. 
                사용자는 복지 제도가 어렵고 복잡해서 너에게 도움을 요청했어.
                제공된 [참고 자료]를 바탕으로, 친구나 가족에게 설명하듯 쉽고 친절하게 답변해줘.

                [엄격한 답변 규칙]
                1. **앵무새 금지:** 참고 자료의 문장을 그대로 복사해서 붙여넣지 마. 내용을 이해한 뒤 너만의 말투로 요약해서 설명해.
                2. **구조화된 답변:** 줄글로 길게 늘어놓지 말고, 가독성 있게 답변해.
                3. **친절한 말투:** "~입니다/합니다" 대신 "~에요/해요" 체를 사용하고, 공감하는 태도를 보여줘.
                4. **출처 준수:** 반드시 [참고 자료]에 있는 내용만 사실로 간주해. 자료에 없는 내용은 "죄송하지만 해당 내용은 자료에 없어 정확한 답변이 어렵습니다."라고 솔직하게 말해.
                5. **이미지 출력:** [참고 자료]에 이미지 링크(http...)가 있다면 답변 끝에 `![설명](주소)` 형식으로 보여줘.
                
                [답변 예시]
                사용자: "생계급여 조건이 뭐야?"
                나쁜 답변: "생계급여 선정기준은 소득인정액이 중위소득 32% 이하인 가구입니다." (X)
                좋은 답변: "생계급여를 받으시려면 소득인정액이 기준 중위소득의 32%보다 적어야 해요! 
                쉽게 말해, 가구원 수에 따른 기준 금액보다 소득인정액이 적으시면 신청 가능합니다.
                
                * **1인 가구:** 82만 원 이하
                * **4인 가구:** 207만 원 이하
                
                모의 계산기를 이용해 보세요! 😊" (O)

                [답변 예시 (스타일 가이드)]
                {few_shot_examples}

                [참고 자료]
                {context_data}
                [사용자 질문]
                {prompt}
                """
                
                response = model.generate_content(system_prompt)
                answer = response.text
                
                message_placeholder.write(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer, "avatar": "💎"})

                is_success = "실패" if "죄송" in answer else "성공"
                log_to_google_form(prompt, answer, is_success)

            except Exception as e:
                if "429" in str(e):
                    st.warning("이용량이 많아 잠시 지연되었습니다. 10초 뒤 다시 시도해주세요.")
                else:
                    st.error(f"오류: {e}")
