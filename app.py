import streamlit as st
import pandas as pd
import requests
import threading
import sys
import subprocess
import google.generativeai as genai

# --------------------------------------------------------------------------
# 1. 기본 설정
# --------------------------------------------------------------------------
st.set_page_config(page_title="복지 챗봇 AI (Pro)", page_icon="⚡")

st.markdown("""
<style>
#MainMenu {visibility: hidden;}
header {visibility: hidden;}
footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --------------------------------------------------------------------------
# 2. 데이터 로드
# --------------------------------------------------------------------------
@st.cache_data
def load_data():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vT3EmDQ002d2Y8dQkgHE4A_wSErUfgK9xU0QJ8pz0yu_W0F7Q9VN1Es-_OKKJjBobIpZr8tBP3aJQ3-/pub?output=csv"
    try:
        df = pd.read_csv(url)
        return df
    except:
        return pd.DataFrame()

# --------------------------------------------------------------------------
# 3. 로그 전송
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
# 4. 메인 로직
# --------------------------------------------------------------------------
# API 키 설정 확인
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
else:
    st.error("API 키가 설정되지 않았습니다.")
    st.stop()

df = load_data()

with st.sidebar:
    st.title("⚡ 복지 상담소")
    st.caption("Premium Model: Gemini 2.0 Flash")
    
    # [키 검증] 키가 제대로 들어갔는지 앞 4자리만 살짝 보여줍니다.
    # (보안상 앞 4자리만 보임. 본인 키랑 맞는지 확인하세요)
    masked_key = api_key[:4] + "****"
    st.code(f"Key: {masked_key}")

st.subheader("⚡ 무엇이든 물어보세요")

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "안녕하세요! 궁금한 점을 물어보세요.", "avatar": "⚡"}]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar=msg.get("avatar")):
        st.write(msg["content"])

if prompt := st.chat_input("질문을 입력하세요"):
    st.session_state.messages.append({"role": "user", "content": prompt, "avatar": "🧑‍💻"})
    with st.chat_message("user", avatar="🧑‍💻"):
        st.write(prompt)

    with st.chat_message("assistant", avatar="⚡"):
        message_placeholder = st.empty()
        
        if df.empty:
            message_placeholder.error("데이터 로드 실패")
            st.stop()

        with st.spinner("분석 중... 🚀"):
            try:
                # [이미지에서 확인된 모델 사용]
                # 사용자님 계정(maxx 프로젝트)에 'gemini-2.0-flash'가 확실히 있습니다.
                model = genai.GenerativeModel("gemini-2.0-flash")

                context_data = df.to_csv(index=False)
                
                system_prompt = f"""
                너는 '복지 정보 상담사'야. 아래 [참고 자료]를 바탕으로만 답변해.
                [참고 자료]
                {context_data}
                [사용자 질문]
                {prompt}
                """
                
                response = model.generate_content(system_prompt)
                answer = response.text
                
                message_placeholder.write(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer, "avatar": "⚡"})

                is_success = "실패" if "죄송" in answer else "성공"
                log_to_google_form(prompt, answer, is_success)

            except Exception as e:
                # 에러 메시지를 좀 더 명확하게
                st.error(f"오류 발생: {e}")
                st.warning("👉 사이드바에 표시된 API 키 앞자리가 유료 프로젝트 키와 일치하는지 확인해주세요.")