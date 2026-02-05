import pandas as pd
import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer
import faiss

# 1. 데이터 로드 및 전처리
df = pd.read_csv("seongsu_rich_rag_data.csv")
# 정보가 없는 행은 제외하고 결합된 텍스트 리스트 생성
documents = df['rich_context'].fillna("정보 없음").tolist()
tokenized_docs = [doc.split(" ") for doc in documents]

# 2. BM25 리트리버 초기화 (키워드 담당)
bm25 = BM25Okapi(tokenized_docs)

# 3. 벡터 리트리버 초기화 (의미 담당)
model = SentenceTransformer('jhgan/ko-sroberta-multitask') # 한국어 성능이 우수한 모델
doc_embeddings = model.encode(documents)

# Faiss 인덱스 생성 (빠른 벡터 검색용)
index = faiss.IndexFlatL2(doc_embeddings.shape[1])
index.add(doc_embeddings.astype('float32'))

def hybrid_search(query, k=5):
    # [BM25 검색]
    tokenized_query = query.split(" ")
    bm25_scores = bm25.get_scores(tokenized_query)
    
    # [Vector 검색]
    query_embedding = model.encode([query])
    distances, indices = index.search(query_embedding.astype('float32'), k * 2)
    
    # 4. RRF (Reciprocal Rank Fusion) 알고리즘으로 순위 통합
    # 각 결과의 순위를 점수로 환산하여 합산 (단순 점수 합산보다 정확함)
    rrf_scores = np.zeros(len(documents))
    
    # BM25 순위 적용
    bm25_ranks = np.argsort(bm25_scores)[::-1]
    for rank, idx in enumerate(bm25_ranks[:k*2]):
        rrf_scores[idx] += 1 / (rank + 60)
        
    # Vector 순위 적용
    for rank, idx in enumerate(indices[0]):
        rrf_scores[idx] += 1 / (rank + 60)
        
    # 최종 결과 정렬
    final_indices = np.argsort(rrf_scores)[::-1][:k]
    return df.iloc[final_indices]

# 5. 테스트 실행
if __name__ == "__main__":
    query = "성수동에서 잠봉뵈르가 맛있는 조용한 빵집 추천해줘"
    results = hybrid_search(query)
    
    print(f"질문: {query}")
    print("="*50)
    for i, row in results.iterrows():
        print(f"{row['place_name']} ({row['category_name']})")
        print(f"요약: {row['rich_context'][:100]}...")
        print("-" * 50)