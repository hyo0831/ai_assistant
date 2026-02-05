import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
import pandas as pd
import time
import random

def crawl_seongsu_baking():
    options = uc.ChromeOptions()
    # 처음 실행 시 눈으로 확인하기 위해 headless 옵션은 끕니다.
    # options.add_argument('--headless') 
    
    try:
        # [핵심 수정] 현재 PC의 크롬 버전인 144를 직접 명시하여 세션 생성 오류를 해결합니다.
        driver = uc.Chrome(options=options, version_main=144)
        print("🚀 브라우저 세션 생성 성공!")
        
    except Exception as e:
        print(f"❌ 드라이버 초기화 실패: {e}")
        print("팁: 'C:/Users/KDA/AppData/Roaming/undetected_chromedriver/' 폴더 내 파일을 삭제 후 재시도해보세요.")
        return

    try:
        # 1. 네이버 모바일 검색 페이지로 이동 (보안 우회에 유리)
        keyword = "성수베이킹스튜디오 후기"
        url = f"https://m.search.naver.com/search.naver?query={keyword}&where=m_blog"
        driver.get(url)
        
        # 사람처럼 보이게 불규칙하게 대기합니다.
        time.sleep(random.uniform(3.0, 5.0)) 

        # 2. 검색 결과 데이터 추출
        results = []
        
        # 블로그 포스트 아이템들을 찾습니다.
        # .api_ani_send는 모바일 네이버 검색 결과의 공통 카드 클래스입니다.
        items = driver.find_elements(By.CSS_SELECTOR, ".api_ani_send")
        
        print(f"🔎 검색 결과 {len(items)}건 발견. 데이터 수집 중...")

        for item in items[:15]: # 상위 15개 정도만 수집
            try:
                # 제목 추출
                title = item.find_element(By.CSS_SELECTOR, ".api_txt_lines").text
                # 요약 내용 추출
                summary = item.find_element(By.CSS_SELECTOR, ".api_txt_contents").text
                
                results.append({
                    "place_name": "성수베이킹스튜디오",
                    "title": title,
                    "summary": summary
                })
            except Exception as inner_e:
                continue
                
        # 3. 데이터 저장
        if results:
            df = pd.DataFrame(results)
            # 한글 깨짐 방지를 위해 utf-8-sig 인코딩을 사용합니다.
            df.to_csv("seongsu_baking_reviews.csv", index=False, encoding="utf-8-sig")
            print(f"✅ 저장 완료: 'seongsu_baking_reviews.csv' ({len(results)}건)")
        else:
            print("⚠️ 수집된 데이터가 없습니다. 셀렉터를 확인하거나 IP 차단 여부를 체크하세요.")

    except Exception as e:
        print(f"❌ 실행 중 오류 발생: {e}")
    finally:
        # 작업 완료 후 브라우저 종료
        time.sleep(3)
        driver.quit()

if __name__ == "__main__":
    crawl_seongsu_baking()