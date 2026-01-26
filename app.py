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
@st.cache_data
def load_data():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vT3EmDQ002d2Y8dQkgHE4A_wSErUfgK9xU0QJ8pz0yu_W0F7Q9VN1Es-_OKKJjBobIpZr8tBP3aJQ3-/pub?output=csv"
    try:
        df = pd.read_csv(url)
        return df
    except:
        return pd.DataFrame()

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
    # 1순위: 사용자님이 원하시는 2.0 (무료 실험 버전)
    try:
        model = genai.GenerativeModel("gemini-2.0-flash-exp")
        model.generate_content("test") # 테스트 발사
        return model, "Gemini 2.0 Flash (Exp)"
    except:
        pass

    # 2순위: 1.5 Flash (가성비 최고)
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        model.generate_content("test")
        return model, "Gemini 1.5 Flash"
    except:
        pass

    # 3순위: 최후의 보루 (이건 구버전 라이브러리에서도 100% 됨)
    try:
        model = genai.GenerativeModel("gemini-pro")
        return model, "Gemini Pro (Legacy)"
    except:
        return None, "Error"

# --------------------------------------------------------------------------
# 6. 메인 로직
# --------------------------------------------------------------------------
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("API 키가 설정되지 않았습니다.")
    st.stop()

df = load_data()

# 모델 로드 시도
model, model_name = get_generative_model()

with st.sidebar:
    st.image("https://bjn.kr/img_bjn/logo2.png", width=200)
    
    if model:
        st.success(f"✅ 연결됨: {model_name}")
    else:
        st.error("❌ 모든 모델 연결 실패 (API키 확인 필요)")

st.image("https://bjn.kr/img_bjn/logo2.png", width=70)

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "안녕하세요. 모의 계산기 관련 문의해 주세요. 일반 복지관련 문의는 복아힘 카페 게시판에 문의 바랍니다.", "avatar": "💎"}]

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
                너는 '복지N 상담사'야. 아래 [참고 자료]를 바탕으로만 답변해.
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