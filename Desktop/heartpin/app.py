import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import os
import faiss

# LlamaIndex 및 RAG 관련 임포트
from llama_index.core import Document, VectorStoreIndex, Settings, StorageContext
from llama_index.retrievers.bm25 import BM25Retriever
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.vector_stores.faiss import FaissVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

# 1. 페이지 설정 (최상단 배치로 즉시 렌더링 유도)
st.set_page_config(page_title="HeartPin", page_icon="💗", layout="centered")

# --- [UI] CSS 스타일 적용 ---
st.markdown("""
<style>
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(180deg, rgba(255,153,204,1) 0%, rgba(153,153,255,1) 50%, rgba(102,204,255,1) 100%);
        background-attachment: fixed;
    }
    [data-testid="stHeader"], [data-testid="stToolbar"] { background-color: rgba(0,0,0,0) !important; }
    p, label, span, div, h2, h3, h1 { color: white !important; text-shadow: 0px 1px 3px rgba(0,0,0,0.3); font-weight: 500; }
    h1 { font-size: 3rem; text-align: center; margin-bottom: 20px; }
    .stButton > button { background-color: rgba(255, 255, 255, 0.2); color: white; border: 1px solid white; border-radius: 20px; width: 100%; transition: 0.3s; }
</style>
""", unsafe_allow_html=True)

# --- [핵심] RAG 엔진 로드 함수 (캐싱 적용) ---
@st.cache_resource
def initialize_heartpin_engine():
    # Secrets 로드
    os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
    os.environ["LANGCHAIN_TRACING_V2"] = st.secrets.get("LANGCHAIN_TRACING_V2", "true")
    os.environ["LANGCHAIN_API_KEY"] = st.secrets.get("LANGCHAIN_API_KEY", "")
    os.environ["LANGCHAIN_PROJECT"] = "HeartPin_Production"
    
    # 임베딩 모델 설정
    Settings.embed_model = HuggingFaceEmbedding(model_name="jhgan/ko-sroberta-multitask")
    
    try:
        # 데이터 로드
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

        vector_store = FaissVectorStore(faiss_index=faiss.IndexFlatL2(768))
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        index = VectorStoreIndex.from_documents(documents, storage_context=storage_context)
        
        system_prompt = "당신은 성수동 베테랑 플래너 'HeartPin'입니다. 구체적인 후기를 인용해 답변하세요."
        
        return index.as_chat_engine(
            chat_mode="context",
            memory=ChatMemoryBuffer.from_defaults(token_limit=3000),
            system_prompt=system_prompt,
            similarity_top_k=5
        )
    except Exception as e:
        st.error(f"엔진 로드 중 오류 발생: {e}")
        return None

# 지도 출력 함수
def display_heartpin_map(map_points, key):
    if not map_points: return
    m = folium.Map(location=[37.5445, 127.0560], zoom_start=15, tiles="CartoDB positron")
    for pt in map_points:
        icon = folium.CustomIcon("logo.png", icon_size=(40, 40)) if os.path.exists("logo.png") else None
        folium.Marker([pt['lat'], pt['lon']], popup=pt['name'], icon=icon).add_to(m)
    st_folium(m, width=700, height=350, key=key, returned_objects=[])

# --- [세션 초기화] ---
if "page" not in st.session_state: st.session_state.page = 1
if "user_profile" not in st.session_state: st.session_state.user_profile = {}
if "messages" not in st.session_state: st.session_state.messages = []

# --- [UI 렌더링 순서: 질문지가 먼저 뜸] ---
if st.session_state.page < 7:
    st.markdown("<h1>Heartpin</h1>", unsafe_allow_html=True)
    
    if st.session_state.page == 1:
        st.subheader("Q1. 오늘 만남은 어떤 사이인가요?")
        rel = st.radio("선택", ["연인(데이트)", "친구(우정)", "썸(설렘)", "가족(외식)"], index=None)
        if st.button("다음"):
            if rel: st.session_state.user_profile["relation"], st.session_state.page = rel, 2
            st.rerun()
    
    elif st.session_state.page == 2:
        st.subheader("Q2. 인당 예산은?")
        bud = st.slider("금액", 10000, 150000, 50000, 10000)
        if st.button("다음"):
            st.session_state.user_profile["budget"], st.session_state.page = f"{bud}원", 3
            st.rerun()

    # ... [Q3~Q5 생략된 질문지 로직 보충] ...
    elif st.session_state.page == 3:
        st.subheader("Q3. 선호 분위기?")
        vibe = st.radio("분위기", ["조용한", "힙한", "고급진"], index=None)
        if st.button("다음"):
            st.session_state.user_profile["vibe"], st.session_state.page = vibe, 4
            st.rerun()

    elif st.session_state.page == 4:
        st.subheader("Q4. MBTI?")
        m1 = st.text_input("나")
        m2 = st.text_input("상대")
        if st.button("다음"):
            st.session_state.user_profile["my_mbti"], st.session_state.user_profile["partner_mbti"], st.session_state.page = m1, m2, 6
            st.rerun()

    elif st.session_state.page == 6:
        st.subheader("Q6. 요청사항?")
        extra = st.text_area("예: 주차")
        if st.button("분석 시작"):
            st.session_state.user_profile["extra"], st.session_state.page = extra, 7
            st.rerun()

# --- [7페이지 진입 시점에 엔진 로드] ---
elif st.session_state.page == 7:
    with st.sidebar:
        if st.button("처음부터"):
            st.session_state.page = 1
            st.session_state.messages = []
            st.rerun()

    # 엔진이 로드되는 동안만 스피너 표시
    with st.spinner("성수동 가이드 'HeartPin'이 깨어나는 중... (약 30초 소요)"):
        chat_engine = initialize_heartpin_engine()

    st.markdown("<h1>Heartpin AI</h1>", unsafe_allow_html=True)
    
    for i, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("map_data"): display_heartpin_map(msg["map_data"], key=f"map_{i}")

    if prompt := st.chat_input("메시지를 입력하세요"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.chat_message("user").markdown(prompt)
        
        with st.chat_message("assistant"):
            p = st.session_state.user_profile
            u_ctx = f"상황:{p['relation']}, 예산:{p['budget']}, MBTI:{p.get('my_mbti')}"
            response = chat_engine.chat(f"[{u_ctx}] {prompt}")
            st.markdown(str(response))
            
            map_data = [{"name": n.node.metadata['name'], "lat": n.node.metadata['lat'], "lon": n.node.metadata['lon']} for n in response.source_nodes]
            if map_data: display_heartpin_map(map_data, key=f"map_{len(st.session_state.messages)}")
            st.session_state.messages.append({"role": "assistant", "content": str(response), "map_data": map_data})
            st.rerun()