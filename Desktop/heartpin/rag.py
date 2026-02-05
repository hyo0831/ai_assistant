# [STEP 1] 최상단 환경 변수 설정 (라이브러리 임포트보다 무조건 앞서야 함)
import os
import streamlit as st

# LangSmith 추적 활성화 (모니터링용)
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
os.environ["LANGCHAIN_API_KEY"] = st.secrets.get("LANGCHAIN_API_KEY", "")
os.environ["LANGCHAIN_PROJECT"] = st.secrets.get("LANGCHAIN_PROJECT", "HeartPin_Production")
os.environ["OPENAI_API_KEY"] = st.secrets.get("OPENAI_API_KEY", "")

# [STEP 2] 필수 라이브러리 임포트
import pandas as pd
import folium
from streamlit_folium import st_folium
import faiss
from llama_index.core import Document, VectorStoreIndex, Settings, StorageContext
from llama_index.retrievers.bm25 import BM25Retriever
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.vector_stores.faiss import FaissVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

# [STEP 3] 페이지 기본 설정
st.set_page_config(page_title="HeartPin", page_icon="💗", layout="centered")

# CSS 스타일 (그라데이션 배경 및 버튼 커스텀)
st.markdown("""
<style>
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(180deg, rgba(255,153,204,1) 0%, rgba(153,153,255,1) 50%, rgba(102,204,255,1) 100%);
        background-attachment: fixed;
    }
    p, label, span, div, h2, h3, h1 { color: white !important; text-shadow: 0px 1px 3px rgba(0,0,0,0.3); font-weight: 500; }
    h1 { font-size: 3rem; text-align: center; margin-bottom: 20px; }
    .stButton > button { background-color: rgba(255, 255, 255, 0.2); color: white; border: 1px solid white; border-radius: 20px; width: 100%; transition: 0.3s; }
</style>
""", unsafe_allow_html=True)

# [STEP 4] RAG 엔진 로드 함수 (캐싱 적용)
@st.cache_resource
def initialize_heartpin_engine():
    # 임베딩 모델 설정
    Settings.embed_model = HuggingFaceEmbedding(model_name="jhgan/ko-sroberta-multitask")
    
    try:
        # 데이터셋 로드
        df = pd.read_csv("seongsu_rich_rag_data.csv")
        df['x'] = pd.to_numeric(df['x'], errors='coerce')
        df['y'] = pd.to_numeric(df['y'], errors='coerce')
        df = df.dropna(subset=['x', 'y'])
        
        documents = []
        for _, row in df.iterrows():
            text = (f"장소: {row['place_name']}\n카테고리: {row['category_name']}\n"
                    f"후기 및 특징: {row['rich_context']}\n주소: {row['road_address_name']}")
            doc = Document(text=text, metadata={"name": row['place_name'], "lat": float(row['y']), "lon": float(row['x'])})
            documents.append(doc)

        # FAISS 벡터 저장소 설정
        vector_store = FaissVectorStore(faiss_index=faiss.IndexFlatL2(768))
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        index = VectorStoreIndex.from_documents(documents, storage_context=storage_context)
        
        system_prompt = (
            "당신은 성수동 베테랑 플래너 'HeartPin'입니다. "
            "데이터셋의 후기를 인용해 구체적으로 답변하세요. "
            "사용자의 상황과 MBTI를 고려하여 친절하게 제안하세요."
        )

        return index.as_chat_engine(
            chat_mode="context",
            memory=ChatMemoryBuffer.from_defaults(token_limit=3000),
            system_prompt=system_prompt,
            similarity_top_k=5
        )
    except Exception as e:
        st.error(f"엔진 초기화 실패: {e}")
        return None

# 지도 출력 함수
def display_heartpin_map(map_points, key):
    if not map_points: return
    m = folium.Map(location=[37.5445, 127.0560], zoom_start=15, tiles="CartoDB positron")
    for pt in map_points:
        icon = folium.CustomIcon("logo.png", icon_size=(40, 40)) if os.path.exists("logo.png") else None
        folium.Marker([pt['lat'], pt['lon']], popup=pt['name'], icon=icon).add_to(m)
    st_folium(m, width=700, height=350, key=key, returned_objects=[])

# [STEP 5] 세션 상태 초기화
if "page" not in st.session_state: st.session_state.page = 1
if "user_profile" not in st.session_state: st.session_state.user_profile = {}
if "messages" not in st.session_state: st.session_state.messages = []

# [STEP 6] 위저드 로직 (Q1~Q6)
if st.session_state.page < 7:
    st.markdown("<h1>Heartpin</h1>", unsafe_allow_html=True)
    
    if st.session_state.page == 1:
        st.subheader("Q1. 오늘 만남은 어떤 사이인가요?")
        rel = st.radio("관계를 선택해주세요", ["연인(데이트)", "친구(우정)", "썸(설렘)", "가족(외식)"], index=None)
        if st.button("다음으로"):
            if rel: 
                st.session_state.user_profile["relation"] = rel
                st.session_state.page = 2
                st.rerun()

    elif st.session_state.page == 2:
        st.subheader("Q2. 인당 예산은 어느 정도인가요?")
        budget = st.slider("금액(원)", 10000, 150000, 50000, 10000)
        if st.button("다음으로"):
            st.session_state.user_profile["budget"] = f"{budget}원"
            st.session_state.page = 3
            st.rerun()

    elif st.session_state.page == 3:
        st.subheader("Q3. 선호하는 분위기는?")
        vibe = st.radio("분위기 선택", ["조용한/대화하기 좋은", "힙한/인스타감성", "에너지넘치는", "고급스러운"], index=None)
        if st.button("다음으로"):
            if vibe:
                st.session_state.user_profile["vibe"] = vibe
                st.session_state.page = 4
                st.rerun()

    elif st.session_state.page == 4:
        st.subheader("Q4. 두 분의 MBTI를 알려주세요")
        c1, c2 = st.columns(2)
        with c1: m1 = st.text_input("나의 MBTI", placeholder="예: INFJ")
        with c2: m2 = st.text_input("상대방 MBTI", placeholder="예: ESTP")
        if st.button("다음으로"):
            st.session_state.user_profile["my_mbti"] = m1 if m1 else "비공개"
            st.session_state.user_profile["partner_mbti"] = m2 if m2 else "비공개"
            st.session_state.page = 5
            st.rerun()

    elif st.session_state.page == 5:
        st.subheader("Q5. 활동성은 어떤가요?")
        act = st.radio("이동 선호도", ["최소한의 이동", "적당히 산책", "많이 걸어도 좋음"], index=None)
        if st.button("다음으로"):
            if act:
                st.session_state.user_profile["activity"] = act
                st.session_state.page = 6
                st.rerun()

    elif st.session_state.page == 6:
        st.subheader("Q6. 특별히 고려해야 할 점이 있나요?")
        extra = st.text_area("예: 주차 필요, 못 먹는 음식, 조용한 구석 자리 등")
        if st.button("HeartPin 분석 시작 ✨"):
            st.session_state.user_profile["extra"] = extra
            st.session_state.page = 7
            st.rerun()

# [STEP 7] 메인 채팅방 로직
elif st.session_state.page == 7:
    with st.sidebar:
        st.markdown("### 📋 선택한 조건")
        p = st.session_state.user_profile
        st.write(f"- 관계: {p['relation']}")
        st.write(f"- 예산: {p['budget']}")
        st.write(f"- MBTI: {p['my_mbti']} & {p['partner_mbti']}")
        if st.button("처음부터 다시하기"):
            st.session_state.page = 1
            st.session_state.messages = []
            st.rerun()

    # 엔진이 준비되는 동안 스피너 표시
    with st.spinner("성수동 전문가 'HeartPin'이 데이터를 분석 중입니다..."):
        chat_engine = initialize_heartpin_engine()

    st.markdown("<h1>Heartpin AI</h1>", unsafe_allow_html=True)

    # 대화 로그 출력
    for i, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("map_data"):
                display_heartpin_map(msg["map_data"], key=f"map_{i}")

    # 채팅 입력
    if prompt := st.chat_input("성수동 코스에 대해 물어보세요!"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.chat_message("user").markdown(prompt)

        with st.chat_message("assistant"):
            p = st.session_state.user_profile
            # 상황 정보를 문맥으로 포함
            context = f"관계:{p['relation']}, 예산:{p['budget']}, 분위기:{p['vibe']}, MBTI:{p['my_mbti']}&{p['partner_mbti']}, 요청:{p['extra']}"
            
            # AI 답변 생성 (이 시점에 LangSmith에 로그가 기록됨)
            response = chat_engine.chat(f"[상황:{context}] 질문:{prompt}")
            st.markdown(str(response))
            
            # 지도 데이터 추출
            map_data = [{"name": n.node.metadata['name'], "lat": n.node.metadata['lat'], "lon": n.node.metadata['lon']} for n in response.source_nodes]
            if map_data:
                display_heartpin_map(map_data, key=f"map_{len(st.session_state.messages)}")
            
            st.session_state.messages.append({"role": "assistant", "content": str(response), "map_data": map_data})
            st.rerun()