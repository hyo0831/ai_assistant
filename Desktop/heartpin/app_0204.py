import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import os
import time
import faiss

# LlamaIndex 및 RAG 관련 임포트
from llama_index.core import Document, VectorStoreIndex, Settings, StorageContext
from llama_index.retrievers.bm25 import BM25Retriever
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.vector_stores.faiss import FaissVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

# 1. 페이지 설정
st.set_page_config(page_title="HeartPin", page_icon="💗", layout="centered")

# --- [핵심] RAG 엔진 로드 및 캐싱 ---
@st.cache_resource
def initialize_heartpin_engine():
    # Secrets에서 API 키 로드
    os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
    os.environ["LANGCHAIN_TRACING_V2"] = st.secrets.get("LANGCHAIN_TRACING_V2", "true")
    os.environ["LANGCHAIN_API_KEY"] = st.secrets.get("LANGCHAIN_API_KEY", "")
    os.environ["LANGCHAIN_PROJECT"] = st.secrets.get("LANGCHAIN_PROJECT", "HeartPin_Production")
    
    # 임베딩 모델 설정
    Settings.embed_model = HuggingFaceEmbedding(model_name="jhgan/ko-sroberta-multitask")
    
    try:
        # 데이터 로드
        df = pd.read_csv(r"seongsu_rich_rag_data.csv")
        df['x'] = pd.to_numeric(df['x'], errors='coerce')
        df['y'] = pd.to_numeric(df['y'], errors='coerce')
        df = df.dropna(subset=['x', 'y'])
        
        documents = []
        for _, row in df.iterrows():
            text = (f"장소: {row['place_name']}\n카테고리: {row['category_name']}\n"
                    f"후기 및 특징: {row['rich_context']}\n주소: {row['road_address_name']}")
            doc = Document(text=text, metadata={"name": row['place_name'], "lat": float(row['y']), "lon": float(row['x'])})
            documents.append(doc)

        # FAISS 인덱스 생성 (768 차원)
        vector_store = FaissVectorStore(faiss_index=faiss.IndexFlatL2(768))
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        index = VectorStoreIndex.from_documents(documents, storage_context=storage_context)
        
        # 시스템 프롬프트 설정
        system_prompt = (
            "당신은 성수동 베테랑 플래너 'HeartPin'입니다. "
            "데이터셋의 '후기 및 특징'을 인용해 구체적으로 답변하세요. "
            "이전에 추천한 장소는 중복되지 않게 노력하세요."
        )

        # 채팅 엔진 생성
        engine = index.as_chat_engine(
            chat_mode="context",
            memory=ChatMemoryBuffer.from_defaults(token_limit=3000),
            system_prompt=system_prompt,
            similarity_top_k=5
        )
        return engine
    except Exception as e:
        st.error(f"엔진 초기화 실패: {e}")
        return None

# 엔진 시동
chat_engine = initialize_heartpin_engine()

# --- [UI] CSS 및 지도 함수 (기존과 동일) ---
st.markdown("""
<style>
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(180deg, rgba(255,153,204,1) 0%, rgba(153,153,255,1) 50%, rgba(102,204,255,1) 100%);
        background-attachment: fixed;
    }
    p, label, span, div, h2, h3, h1 { color: white !important; text-shadow: 0px 1px 3px rgba(0,0,0,0.3); }
    .stButton > button { background-color: rgba(255, 255, 255, 0.2); color: white; border: 1px solid white; border-radius: 20px; width: 100%; }
</style>
""", unsafe_allow_html=True)

def display_heartpin_map(map_points, key):
    m = folium.Map(location=[37.5445, 127.0560], zoom_start=15, tiles="CartoDB positron")
    for pt in map_points:
        icon = folium.CustomIcon("logo.png", icon_size=(40, 40)) if os.path.exists("logo.png") else None
        folium.Marker([pt['lat'], pt['lon']], popup=pt['name'], icon=icon).add_to(m)
    st_folium(m, width=700, height=350, key=key, returned_objects=[])

# --- [Main Logic] 위저드 및 채팅 ---
if "page" not in st.session_state: st.session_state.page = 1
if "user_profile" not in st.session_state: st.session_state.user_profile = {}
if "messages" not in st.session_state: st.session_state.messages = []

if st.session_state.page < 7:
    st.markdown("<h1>Heartpin</h1>", unsafe_allow_html=True)
    # [Q1~Q6 로직 생략 없이 기존 코드 적용]
    # ... (질문지 구성 생략) ...
    # 질문지가 끝나면 st.session_state.page = 7로 변경

elif st.session_state.page == 7:
    # 채팅방 인터페이스
    for i, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("map_data"):
                display_heartpin_map(msg["map_data"], key=f"map_{i}")

    if prompt := st.chat_input("성수동 코스를 물어보세요..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.chat_message("user").markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("HeartPin 분석 중..."):
                p = st.session_state.user_profile
                user_context = f"관계:{p['relation']}, 예산:{p['budget']}, MBTI:{p['my_mbti']}"
                response = chat_engine.chat(f"[상황:{user_context}] 질문:{prompt}")
                
                st.markdown(str(response))
                map_data = [{"name": n.node.metadata['name'], "lat": n.node.metadata['lat'], "lon": n.node.metadata['lon']} for n in response.source_nodes]
                
                if map_data:
                    display_heartpin_map(map_data, key=f"map_{len(st.session_state.messages)}")
                
                st.session_state.messages.append({"role": "assistant", "content": str(response), "map_data": map_data})
                st.rerun()