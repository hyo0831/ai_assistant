import os
import sys
import urllib.request
import urllib.parse
import json
import pandas as pd
import time
import re

# 1. 네이버 API 인증 정보
CLIENT_ID = ""
CLIENT_SECRET = ""

def clean_html(raw_html):
    """HTML 태그와 특수 문자를 제거하여 깨끗한 텍스트를 만듭니다."""
    clean_text = re.sub('<.*?>', '', raw_html) # 태그 제거
    clean_text = re.sub('&#39;', "'", clean_text) # 작은따옴표 복원
    clean_text = re.sub('&quot;', '"', clean_text) # 큰따옴표 복원
    return clean_text

def get_blog_reviews(place_name):
    """가게 이름을 입력받아 네이버 블로그 검색 결과(요약)를 가져옵니다."""
    encText = urllib.parse.quote(f"성수 {place_name} 후기")
    url = f"https://openapi.naver.com/v1/search/blog?query={encText}&display=10&sort=sim"
    
    request = urllib.request.Request(url)
    request.add_header("X-Naver-Client-Id", CLIENT_ID)
    request.add_header("X-Naver-Client-Secret", CLIENT_SECRET)
    
    try:
        response = urllib.request.urlopen(request)
        if response.getcode() == 200:
            data = json.loads(response.read().decode('utf-8'))
            items = data.get('items', [])
            
            # 여러 개의 블로그 후기를 하나의 긴 텍스트로 합칩니다 (RAG context용)
            combined_reviews = ""
            for item in items:
                title = clean_html(item['title'])
                description = clean_html(item['description'])
                combined_reviews += f"{title}: {description} "
            
            return combined_reviews.strip() if combined_reviews else "정보 없음"
        else:
            return f"Error: {response.getcode()}"
    except Exception as e:
        return f"Exception: {str(e)}"

def main():
    # 2. 원본 가게 리스트 로드
    df = pd.read_csv(r"C:\Users\KDA\OneDrive\Documents\seongsu_date_spots.csv")
    print(f"📂 총 {len(df)}개 가게 데이터 수집을 시작합니다.")

    rich_contexts = []

    # 3. 루프를 돌며 데이터 수집
    for i, name in enumerate(df['place_name']):
        print(f"[{i+1}/{len(df)}] '{name}' 수집 중...")
        
        review_text = get_blog_reviews(name)
        rich_contexts.append(review_text)
        
        # API 과부하 방지 및 차단 방지를 위한 짧은 휴식 (초당 5~10회 권장)
        time.sleep(0.1)

    # 4. 결과 저장
    df['rich_context'] = rich_contexts
    output_file = "seongsu_rich_rag_data.csv"
    df.to_csv(output_file, index=False, encoding="utf-8-sig")
    
    print(f"\n✅ 모든 수집이 완료되었습니다! 파일명: {output_file}")

if __name__ == "__main__":
    main()