import streamlit as st
import requests
import time
import pandas as pd
import folium
from streamlit_folium import st_folium
import os

# 1. 페이지 설정
st.set_page_config(page_title="HeartPin", page_icon="💗", layout="centered")

# ==========================================
# [CSS] Heartpin Identity 스타일 (기존 동일)
# ==========================================
heartpin_css = """
<style>
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(180deg, rgba(255,153,204,1) 0%, rgba(153,153,255,1) 50%, rgba(102,204,255,1) 100%);
        background-attachment: fixed;
    }
    [data-testid="stHeader"], [data-testid="stToolbar"] { background-color: rgba(0,0,0,0) !important; }
    .stTextInput, .stSelectbox, .stSlider, .stRadio, .stTextArea { background-color: transparent !important; }
    p, label, span, div, h2, h3 { color: white !important; text-shadow: 0px 1px 3px rgba(0,0,0,0.3); font-weight: 500; }
    h1 { color: white !important; font-family: 'Helvetica', sans-serif; font-weight: 700; text-align: center; text-shadow: 0px 2px 5px rgba(0,0,0,0.2); margin-bottom: 30px; }
    .stButton > button { background-color: rgba(255, 255, 255, 0.2); color: white; border: 1px solid white; border-radius: 20px; width: 100%; transition: 0.3s; }
    .stButton > button:hover { background-color: rgba(255, 255, 255, 0.4); border-color: white; color: white; }
    [data-testid="stSidebar"] { background-color: rgba(255, 255, 255, 0.1); }
</style>
"""
st.markdown(heartpin_css, unsafe_allow_html=True)

# 2. 세션 상태 초기화
if "page" not in st.session_state: st.session_state.page = 1
if "user_profile" not in st.session_state: st.session_state.user_profile = {}
if "messages" not in st.session_state: st.session_state.messages = []

# 3. 커스텀 지도 출력 함수 (고유 키 적용)
def display_heartpin_map(map_points, key):
    if not map_points:
        return
    
    # 지도 생성
    m = folium.Map(location=[37.5445, 127.0560], zoom_start=15, tiles="CartoDB positron")
    
    logo_path = "logo.png"
    
    for point in map_points:
        if os.path.exists(logo_path):
            icon = folium.CustomIcon(logo_path, icon_size=(40, 40))
        else:
            icon = folium.Icon(color='lightred', icon='heart', prefix='fa')

        folium.Marker(
            [point['lat'], point['lon']],
            popup=folium.Popup(f"<b>{point['name']}</b>", max_width=200),
            icon=icon
        ).add_to(m)
    
    # st_folium에 고유 key를 부여하여 이전 지도와 충돌 방지
    st_folium(m, width=700, height=350, key=key, returned_objects=[])

# ==========================================
# [Step 1-6] 위저드 로직 (생략 없이 포함)
# ==========================================
if st.session_state.page < 7:
    st.markdown("<h1>Heartpin</h1>", unsafe_allow_html=True)
    total_steps = 6 
    current_progress = (st.session_state.page - 1) / total_steps
    st.progress(current_progress)
    st.divider()

    if st.session_state.page == 1:
        st.subheader("Q1. 오늘 만남은 어떤 사이인가요?")
        relation = st.radio("하나만 선택해주세요", ["연인(데이트)", "친구(우정)", "썸(설렘)", "가족(외식)", "비즈니스(미팅)"], index=None)
        if st.button("다음으로 넘어가주세요!"):
            if relation: 
                st.session_state.user_profile["relation"] = relation
                st.session_state.page = 2
                st.rerun()

    elif st.session_state.page == 2:
        st.subheader("Q2. 인당 예산은 어느 정도인가요?")
        budget_val = st.slider("금액 설정 (단위: 원)", 10000, 150000, 50000, 10000, format="%d원")
        if st.button("다음으로 넘어가주세요!"):
            st.session_state.user_profile["budget"] = f"{budget_val}원"
            st.session_state.page = 3
            st.rerun()

    elif st.session_state.page == 3:
        st.subheader("Q3. 선호하는 분위기는?")
        vibe = st.radio("가장 중요한 무드를 골라주세요", ["대화하기 좋은(조용)", "힙한", "에너지넘치는", "고급스러운", "이국적인"], index=None)
        if st.button("다음으로 넘어가주세요!"):
            if vibe:
                st.session_state.user_profile["vibe"] = vibe
                st.session_state.page = 4
                st.rerun()

    elif st.session_state.page == 4:
        st.subheader("Q4. 이동 동선은 어떻게 할까요?")
        activity = st.radio("활동성을 선택해주세요", ["최소한의 이동", "적당히 산책", "많이 걸어도 좋음"], index=None)
        if st.button("다음으로 넘어가주세요!"):
            if activity:
                st.session_state.user_profile["activity"] = activity
                st.session_state.page = 5
                st.rerun()

    elif st.session_state.page == 5:
        st.subheader("Q5. 두 분의 MBTI를 알려주세요")
        col1, col2 = st.columns(2)
        with col1: m_me = st.text_input("나의 MBTI", placeholder="예: ENTJ")
        with col2: m_you = st.text_input("상대방 MBTI", placeholder="예: ISFP")
        if st.button("다음으로 넘어가주세요!"):
            st.session_state.user_profile["my_mbti"] = m_me if m_me else "기재안함"
            st.session_state.user_profile["partner_mbti"] = m_you if m_you else "기재안함"
            st.session_state.page = 6
            st.rerun()

    elif st.session_state.page == 6:
        st.subheader("Q6. 마지막으로 특별히 요청할 사항이 있나요?")
        extra = st.text_area("알러지, 주차 여부 등 자유롭게 적어주세요.")
        if st.button("Heartpin 분석 시작 ✨"):
            st.session_state.user_profile["extra_info"] = extra
            st.session_state.page = 7
            st.rerun()

# ==========================================
# [Step 7] 메인 채팅방 (말풍선별 지도 독립 출력)
# ==========================================
elif st.session_state.page == 7:
    with st.sidebar:
        st.markdown("<h2 style='color:white;'>My Profile</h2>", unsafe_allow_html=True)
        p = st.session_state.user_profile
        st.info(f"목적: {p.get('relation')}\n\n예산: {p.get('budget')}\n\nMBTI: {p.get('my_mbti')} & {p.get('partner_mbti')}")
        if st.button("처음부터 다시하기"):
            st.session_state.page = 1
            st.session_state.messages = []
            st.rerun()

    st.markdown("<h1>Heartpin AI</h1>", unsafe_allow_html=True)

    # 대화 로그 출력 루프 (enumerate를 사용하여 고유 인덱스 확보)
    for i, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            # 해당 메시지에 맵 데이터가 있고, 어시스턴트의 답변인 경우에만 지도를 바로 아래 출력
            if msg.get("map_data"):
                # 각 지도에 고유한 key(예: map_0, map_2...)를 부여하여 데이터 혼선을 방지
                display_heartpin_map(msg["map_data"], key=f"map_{i}")

    # 초기 환영 인사 생성
    if not st.session_state.messages:
        welcome = (f"반갑습니다! {p['my_mbti']} 성향에 맞춘 {p['relation']} 코스를 준비했습니다. "
                   f"설정한 {p['budget']} 내에서 성수동의 숨은 명소들을 추천해 드릴까요?")
        st.session_state.messages.append({"role": "assistant", "content": welcome})
        st.rerun()

    # 채팅 입력
    if prompt := st.chat_input("HeartPin에게 코스를 물어보세요..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.chat_message("user").markdown(prompt)

        with st.chat_message("assistant"):
            try:
                with st.spinner("최적의 장소를 핀 찍는 중..."):
                    res = requests.post("http://127.0.0.1:8000/recommend_v2", 
                                        json={**st.session_state.user_profile, "user_query": prompt}, timeout=25)
                
                if res.status_code == 200:
                    data = res.json()
                    st.markdown(data['response'])
                    
                    # 새 답변에 대한 지도를 즉시 출력
                    if data.get('map_points'):
                        # 새 메시지가 추가될 인덱스를 미리 계산하여 키로 사용
                        new_key = f"map_{len(st.session_state.messages)}"
                        display_heartpin_map(data['map_points'], key=new_key)
                    
                    # 메시지 리스트에 데이터 저장
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": data['response'], 
                        "map_data": data.get('map_points')
                    })
                    st.rerun() # 화면 갱신을 통해 순서 고정
                else:
                    st.error("서버 응답 에러")
            except Exception as e:
                st.error(f"서버 연결 실패: {e}")