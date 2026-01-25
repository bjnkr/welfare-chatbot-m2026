import streamlit as st
import pandas as pd
import google.generativeai as genai

# 페이지 설정
st.set_page_config(page_title="복지 챗봇 AI", page_icon="🤖")

# 사이드바: API 키 입력
with st.sidebar:
    st.header("설정")
    api_key = st.text_input("Gemini API Key", type="password", help="Google AI Studio에서 발급받은 키를 입력하세요.")
    if api_key:
        genai.configure(api_key=api_key)
        st.success("API 키가 설정되었습니다!")
    else:
        st.warning("API 키를 입력해야 챗봇이 작동합니다.")
        st.markdown("[API 키 발급받기](https://aistudio.google.com/app/apikey)")

# 제목
st.title("🤖 지능형 복지 챗봇")
st.caption("AI가 구글 시트 데이터를 분석하여 답변해드립니다.")

# 데이터 로드 함수 (캐싱하여 성능 최적화)
@st.cache_data
def load_data():
    # 구글 시트 데이터 URL
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vT3EmDQ002d2Y8dQkgHE4A_wSErUfgK9xU0QJ8pz0yu_W0F7Q9VN1Es-_OKKJjBobIpZr8tBP3aJQ3-/pub?output=csv"
    
    try:
        df = pd.read_csv(url)
        return df
    except Exception as e:
        st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
        return pd.DataFrame()

# 데이터 불러오기
df = load_data()

# 채팅 기록 초기화
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "안녕하세요! 복지 정보에 대해 무엇이든 물어보세요."}]

# 채팅 메시지 표시
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# 사용자 입력 처리
if prompt := st.chat_input("질문을 입력하세요 (예: 양육비 언제 받을 수 있어?)"):
    # 사용자 메시지 표시
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    # 봇 응답 생성
    if not api_key:
        st.error("왼쪽 사이드바에 Gemini API 키를 먼저 입력해주세요.")
    elif df.empty:
        st.error("데이터가 로드되지 않았습니다.")
    else:
        with st.chat_message("assistant"):
            with st.spinner("AI가 자료를 분석 중입니다..."):
                try:
                    # 1. 데이터프레임을 문자열로 변환 (전체 컨텍스트)
                    # to_csv로 변환하여 AI가 구조를 이해하기 쉽게 함
                    context_data = df.to_csv(index=False)
                    
                    # 2. 프롬프트 구성
                    system_prompt = f"""
                    [시스템 지시사항]
                    너는 친절하고 정확한 복지 상담사야. 아래 [참고 자료]를 꼼꼼히 읽고 사용자의 질문에 답변해줘.
                    
                    규칙:
                    1. 반드시 [참고 자료]에 있는 내용에 기반해서만 대답해야 해.
                    2. 자료에 없는 내용은 절대 지어내지 말고, "죄송합니다. 제공된 자료에는 해당 내용이 없습니다."라고 정중하게 말해.
                    3. 답변은 이해하기 쉽게 요약해서 설명해주고, 필요하다면 구체적인 조건이나 금액도 언급해줘.
                    
                    [참고 자료]
                    {context_data}
                    
                    [사용자 질문]
                    {prompt}
                    """
                    
                    # 3. Gemini 모델 호출
                    model = genai.GenerativeModel("gemini-2.0-flash")
                    response = model.generate_content(system_prompt)
                    
                    # 4. 결과 출력
                    answer = response.text
                    st.write(answer)
                    
                    # 세션에 저장
                    st.session_state.messages.append({"role": "assistant", "content": answer})
                    
                except Exception as e:
                    st.error(f"AI 응답 생성 중 오류가 발생했습니다: {e}")
