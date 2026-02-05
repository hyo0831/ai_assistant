import pandas as pd
import re

def refine_dataset(file_path):
    df = pd.read_csv(file_path)
    
    def refiner(text):
        if pd.isna(text): return ""
        # 1. HTML 태그 제거 (이미 하셨을 수도 있지만 한 번 더)
        text = re.sub(r'<[^>]+>', '', text)
        # 2. 블로그 상투적인 문구 제거 (인사, 일상 얘기)
        text = re.sub(r'(안녕하세요|반가워요|포스팅|블로거|이웃|일상|오늘).*?(예요|입니다|했는데요|할게요)', '', text)
        # 3. 특수문자 및 과도한 공백 정리
        text = re.sub(r'[^가-힣a-zA-Z0-9\s,.!]', '', text)
        # 4. 공백 제거
        text = re.sub(' ', '', text)
        return text.strip()

    df['cleaned_context'] = df['rich_context'].apply(refiner)
    df.to_csv(r"C:\Users\KDA\Desktop\heartpin\seongsu_rich_rag_data.csv", index=False, encoding="utf-8-sig")
    print("✨ 노이즈가 제거된 RAG 전용 데이터셋 생성 완료!")

refine_dataset("seongsu_rich_rag_data.csv")