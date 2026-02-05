url = "https://dapi.kakao.com/v2/local/search/category.json"

import requests
import pandas as pd
import time

class KakaoDataCollector:
    def __init__(self, api_key):
        self.api_key = api_key
        self.headers = {"Authorization": f"KakaoAK {'33313e75a1e6a81d198d7fa4ae169c95'}"}
        self.url = "https://dapi.kakao.com/v2/local/search/keyword.json"

    def collect_seongsu_data(self, keywords):
        all_results = []
        
        for kw in keywords:
            print(f"--- '{kw}' 키워드 수집 시작 ---")
            for page in range(1, 4):  # 카카오는 최대 3페이지(45개)까지 제공
                params = {
                    "query": f"성수동 {kw}",
                    "page": page,
                    "size": 15
                }
                response = requests.get(self.url, headers=self.headers, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    documents = data.get('documents', [])
                    
                    if not documents:
                        break
                        
                    for doc in documents:
                        all_results.append({
                            "place_id": doc['id'],
                            "place_name": doc['place_name'],
                            "category_name": doc['category_name'],
                            "category_group": doc['category_group_name'],
                            "address_name": doc['address_name'],
                            "road_address_name": doc['road_address_name'],
                            "phone": doc['phone'],
                            "place_url": doc['place_url'],
                            "x": float(doc['x']),
                            "y": float(doc['y']),
                            "collected_kw": kw
                        })
                    
                    if data.get('meta', {}).get('is_end'):
                        break
                    
                    time.sleep(0.2) # API 과부하 방지
                else:
                    print(f"Error: {response.status_code}")
                    break
                    
        # 데이터프레임 변환 및 중복 제거 (place_id 기준)
        df = pd.DataFrame(all_results)
        df = df.drop_duplicates(subset=['place_id']).reset_index(drop=True)
        return df

# --- 실행부 ---
if __name__ == "__main__":
    # 1. 본인의 REST API 키를 입력하세요
    KAKAO_REST_API_KEY = "YOUR_REST_API_KEY_HERE"
    
    # 2. PdM의 시나리오를 고려한 전략적 키워드 선정
    search_keywords = ["맛집", "카페", "와인바", "소품샵", "팝업스토어", "전시회", "데이트"]
    
    collector = KakaoDataCollector(KAKAO_REST_API_KEY)
    seongsu_df = collector.collect_seongsu_data(search_keywords)
    
    # 3. 데이터 확인 및 CSV 저장
    print(f"\n총 {len(seongsu_df)}개의 유니크한 장소를 수집했습니다.")
    print(seongsu_df.head())
    
    seongsu_df.to_csv("seongsu_date_spots.csv", index=False, encoding="utf-8-sig")
    print("\n'seongsu_date_spots.csv' 파일로 저장 완료되었습니다.")