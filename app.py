import streamlit as st
import pandas as pd
import google.generativeai as genai
import requests
import threading
import sys

# --------------------------------------------------------------------------
# 1. 기본 설정 및 디자인
# --------------------------------------------------------------------------
st.set_page_config(page_title="복지 챗봇 AI", page_icon="🧚‍♀️")

st.markdown("""
<style>
#MainMenu {visibility: hidden;}
header {visibility: hidden;}
footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --------------------------------------------------------------------------
# 2. 핵심 기능: 구글 시트 데이터 로드
# --------------------------------------------------------------------------
@st.cache_data
def load_data():
    # 사용자님의 구글 시트 CSV 주소
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vT3EmDQ002d2Y8dQkgHE4A_wSErUfgK9xU0QJ8pz0yu_W0F7Q9VN1Es-_OKKJjBobIpZr8tBP3aJQ3-/pub?output=csv"
    try:
        df = pd.read_csv(url)
        return df
    except:
        return pd.DataFrame()

# --------------------------------------------------------------------------
# 3. 모델 자동 선택기 (에러 방지용)
# --------------------------------------------------------------------------
def get_best_model():
    # 1순위: 1.5 Flash (데이터 분석에 최적)
    # 2순위: 1.0 Pro (안정성)
    try:
        preferred_order = ["gemini-1.5-flash", "gemini-1.0-pro", "gemini-pro"]
        available_models = [m.name for m in genai.list_models()]
        
        for preferred in preferred_order:
            for model_name in available_models:
                if preferred in model_name:
                    return model_name
        return "gemini-pro"
    except:
        return "gemini-pro"

# --------------------------------------------------------------------------
# 4. 로그 전송 함수
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
# 5. 메인 로직
# --------------------------------------------------------------------------
# API 키 설정
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("API 키가 없습니다.")
    st.stop()

# 데이터 불러오기
df = load_data()

# 사이드바
with st.sidebar:
    st.title("🧚‍♀️ 복지 상담소")
    st.info("구글 시트 데이터를 분석하여 답변합니다.")

# 채팅 UI
st.subheader("✨ 무엇이든 물어보세요")

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "안녕하세요! 복지 혜택에 대해 궁금한 점을 물어보세요.", "avatar": "🧚‍♀️"}]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar=msg.get("avatar")):
        st.write(msg["content"])

# 질문 처리
if prompt := st.chat_input("질문을 입력하세요"):
    st.session_state.messages.append({"role": "user", "content": prompt, "avatar": "🧑‍💻"})
    with st.chat_message("user", avatar="🧑‍💻"):
        st.write(prompt)

    with st.chat_message("assistant", avatar="🧚‍♀️"):
        message_placeholder = st.empty()
        
        if df.empty:
            message_placeholder.error("데이터를 불러오지 못했습니다.")
            st.stop()

        with st.spinner("자료를 찾아보고 있어요... 💬"):
            try:
                # [중요] 데이터를 텍스트로 변환해서 프롬프트에 넣기
                context_data = df.to_csv(index=False)
                
                # [강력한 제약 조건] 자료에 없으면 절대 대답하지 말라고 지시
                system_prompt = f"""
                너는 '복지 정보 상담사'야. 아래 [참고 자료]를 바탕으로만 답변해.
                
                [엄격한 규칙]
                1. 반드시 제공된 [참고 자료]에 있는 내용만 사용해.
                2. 자료에 없는 내용은 절대 지어내지 말고, "죄송합니다. 제공된 자료에는 해당 정보가 없습니다."라고 말해.
                3. 사용자의 질문과 가장 관련 있는 혜택을 찾아서 요약해줘.

                [참고 자료]
                {context_data}

                [사용자 질문]
                {prompt}
                """
                
                # 모델 선택 및 실행
                best_model = get_best_model()
                model = genai.GenerativeModel(best_model)
                response = model.generate_content(system_prompt)
                answer = response.text
                
                message_placeholder.write(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer, "avatar": "🧚‍♀️"})

                # 로그 전송
                is_success = "실패" if "죄송" in answer else "성공"
                log_to_google_form(prompt, answer, is_success)

            except Exception as e:
                st.error(f"오류: {e}")