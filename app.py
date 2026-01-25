import streamlit as st
import pandas as pd
import google.generativeai as genai
import requests
import threading
import time

# --------------------------------------------------------------------------
# 1. 구글 폼 로그 전송 함수 (비동기 처리)
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
            requests.post(form_url, data=data, timeout=5)
        except:
            pass 

    thread = threading.Thread(target=send_request)
    thread.start()

# --------------------------------------------------------------------------
# 2. 페이지 설정
# --------------------------------------------------------------------------
st.set_page_config(page_title="복지 챗봇 AI", page_icon="🤖")

st.markdown("""
<style>
#MainMenu {visibility: hidden;}
header {visibility: hidden;}
footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --------------------------------------------------------------------------
# 3. 모델 설정 및 데이터 로드
# --------------------------------------------------------------------------
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("API 키가 설정되지 않았습니다.")

@st.cache_data
def load_data():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vT3EmDQ002d2Y8dQkgHE4A_wSErUfgK9xU0QJ8pz0yu_W0F7Q9VN1Es-_OKKJjBobIpZr8tBP3aJQ3-/pub?output=csv"
    try:
        df = pd.read_csv(url)
        return df
    except:
        return pd.DataFrame()

df = load_data()

# --------------------------------------------------------------------------
# 4. 메인 UI
# --------------------------------------------------------------------------
with st.sidebar:
    st.markdown("복지N 챗봇입니다")

st.subheader("✨ 계산기 관련 질문해주세요")

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "안녕하세요! 복지N 입니다 계산기 관련 문의해 주세요."}]

for msg in st.session_state.messages:
    avatar = "🧚" if msg["role"] == "assistant" else "🧑"
    with st.chat_message(msg["role"], avatar=avatar):
        st.write(msg["content"])

# --------------------------------------------------------------------------
# 5. 질문 처리 (모델 Fallback 로직 적용)
# --------------------------------------------------------------------------
if prompt := st.chat_input("질문을 입력하세요..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🧑"):
        st.write(prompt)

    with st.chat_message("assistant", avatar="🧚"):
        message_placeholder = st.empty()
        
        if df.empty:
            message_placeholder.error("데이터를 불러올 수 없습니다.")
            st.stop()

        with st.spinner("관련 정보를 열심히 찾고 있어요... 💬"):
            try:
                # 1. 전체 데이터 컨텍스트 (Flash 모델은 대용량 처리에 강함)
                full_data = df.to_csv(index=False)
                
                system_prompt = f"""
                너는 유능한 사회복지 상담사야. 아래 [참고 자료]를 바탕으로 답변해줘.

                [참고 자료]
                {full_data}

                [규칙]
                1. 반드시 제공된 자료에 있는 내용으로만 답변해.
                2. 자료에 없으면 "죄송합니다. 방금하신 질문은 게시판에 문의 바랍니다."라고 답해.
                3. 핵심만 간결하고 친절하게 답변해.

                [질문]
                {prompt}
                """
                
                # 2. 모델 시도 (2.0 Exp -> 실패 시 1.5 Flash -> 실패 시 1.5 Pro)
                try:
                    # 1순위: 가장 빠르고 똑똑한 2.0 Flash Exp
                    model = genai.GenerativeModel("gemini-2.0-flash-exp")
                    response = model.generate_content(system_prompt)
                    answer = response.text
                except Exception as e:
                    # 2순위: 안정적인 1.5 Flash
                    # st.toast(f"2.0 모델 사용 불가, 1.5로 전환합니다. ({e})") # 디버깅용
                    model = genai.GenerativeModel("gemini-1.5-flash")
                    response = model.generate_content(system_prompt)
                    answer = response.text
                
                message_placeholder.write(answer)

                # 답변 저장 & 로그
                st.session_state.messages.append({"role": "assistant", "content": answer})
                status = "실패" if "죄송합니다" in answer else "성공"
                log_to_google_form(prompt, answer, status)

            except Exception as e:
                message_placeholder.error(f"오류가 발생했습니다: {e}")
                log_to_google_form(prompt, f"System Error: {e}", "에러")