import sys
from pykiwoom.kiwoom import Kiwoom
import pandas as pd
from datetime import datetime, timedelta

def run_test():
    # 1. 키움 객체 생성 및 로그인
    # 실행 시 로그인 창이 뜨면 모의투자인지 실전인지 체크하고 로그인하세요.
    kiwoom = Kiwoom()
    kiwoom.CommConnect(block=True)
    
    print("\n" + "="*50)
    print(" [ORION] 키움증권 데이터 수집 테스트 시작")
    print("="*50)

    # 2. 접속 정보 확인 (실전/모의 구분)
    server_type = kiwoom.GetConnectState() # 1이면 연결됨
    is_demo = kiwoom.GetLoginInfo("GetServerGubun") # "1"이면 모의투자, 나머지 실전
    
    mode_str = "모의투자" if is_demo == "1" else "실전매매"
    print(f"▶ 현재 접속 모드: {mode_str}")

    # 3. 계좌 정보 가져오기
    accounts = kiwoom.GetLoginInfo("ACCNO")
    # 계좌가 여러 개일 수 있으므로 첫 번째 계좌 사용
    account_num = accounts[0].strip(';') 
    print(f"▶ 사용 계좌번호: {account_num}")

    # 4. 날짜 설정 (최근 30일)
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
    print(f"▶ 조회 기간: {start_date} ~ {end_date}")
    print("▶ 데이터 분석 중... 잠시만 기다려 주세요.")

    # 5. [데이터 가공] 30일치 일자별 실적 현황 (TR: opt10074)
    # 이 TR은 일자별로 매수금액, 매도금액, 수익을 한눈에 보여줍니다.
    df = kiwoom.block_request("opt10074",
                              계좌번호=account_num,
                              시작일자=start_date,
                              종료일자=end_date,
                              output="일자별실적현황",
                              next=0)

    # 6. 결과 출력 (터미널)
    if df is not None and not df.empty:
        # 출력용 데이터 정리 (데이터가 문자열로 오기 때문에 숫자로 변환)
        df['당일매수금액'] = pd.to_numeric(df['당일매수금액'])
        df['당일매도금액'] = pd.to_numeric(df['당일매도금액'])
        df['당일실현손익'] = pd.to_numeric(df['당일실현손익'])

        print("\n" + "-"*50)
        print(f"{'일자':<10} | {'매수금액':<12} | {'매도금액':<12} | {'실현손익':<10}")
        print("-"*50)

        for _, row in df.iterrows():
            print(f"{row['일자']:<10} | {row['당일매수금액']:>12,.0f} | {row['당일매도금액']:>12,.0f} | {row['당일실현손익']:>10,.0f}")

        total_profit = df['당일실현손익'].sum()
        print("-"*50)
        print(f"▶ 30일간 총 누적 손익: {total_profit:,.0f}원")
        print("="*50)
        
        if total_profit > 0:
            print("🎉 분석 결과: 당신은 '상위 티어'의 가능성이 보입니다!")
        else:
            print("📉 분석 결과: 리스크 관리가 필요합니다. '아이언' 등급 예상.")
    else:
        print("\n[!] 해당 기간에 매매 기록이 없습니다.")

if __name__ == "__main__":
    # 키움 API는 32비트 파이썬에서만 동작합니다.
    if sys.maxsize > 2**32:
        print("[오류] 64비트 파이썬입니다. 32비트 환경에서 실행해주세요.")
    else:
        run_test()