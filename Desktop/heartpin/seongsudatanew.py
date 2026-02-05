import pandas as pd

# 1. 파일 불러오기
df = pd.read_csv("seongsu_date_spots.csv")

# 2. 전처리: category_name에서 '대분류' 추출 (예: 음식점 > 일식 -> 음식점)
# 카카오의 category_name은 매우 상세하므로, 첫 번째 단어를 가져오는 것이 분류에 유리합니다.
df['main_category'] = df['category_name'].apply(lambda x: x.split(' > ')[0])

# 3. 중복 데이터 및 불필요한 컬럼 정리
# collected_kw는 'search_context'라는 이름으로 변경하여 LLM이 참고만 하게 함
df.rename(columns={'collected_kw': 'search_context'}, inplace=True)

# 4. 결과 확인
print(df['main_category'].value_counts()) # 어떤 분류가 얼마나 있는지 확인
df.to_csv("seongsu_cleaned.csv", index=False, encoding="utf-8-sig")