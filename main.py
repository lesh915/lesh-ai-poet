# 환경 변수
# from dotenv import load_dotenv
# load_dotenv()

# 스트림릿
import streamlit as st
# ChatOpenAI
from langchain.chat_models import ChatOpenAI

# ChatGPT 인공지능에게 시를 요청하기
chat_model = ChatOpenAI()
# content = "호주 여행"
# result = chat_model.predict(content + "에 대한 시를 써줘")
# print(result)

# 인공지능 시인 화면 구성하기
st.title('인공지능 시인')
content = st.text_input('시의 주제를 제시해주세요.', '')

if st.button('시 작성 요청하기'):
    with st.spinner('시 작성 중...'):
        result = chat_model.predict("write a poet" + content + "에 대한 시를 써줘")
        st.write(result)