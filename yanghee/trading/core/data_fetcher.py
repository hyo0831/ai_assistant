import yfinance as yf
import pandas as pd


def fetch_stock_data(ticker: str, period: str = "3y", interval: str = "1wk") -> pd.DataFrame:
    """
    yfinance를 사용하여 주가 데이터 다운로드

    Args:
        ticker: 종목 코드 (예: "AAPL", "TSLA", "005930.KS")
        period: 데이터 기간 (기본: 3년 - 주봉 분석에 적합)
        interval: 데이터 간격 (기본: '1wk' 주봉, '1d' 일봉, '1mo' 월봉)

    Returns:
        OHLCV 데이터프레임
    """
    print(f"[*] Fetching {interval} data for {ticker} (period: {period})...")
    stock = yf.Ticker(ticker)
    df = stock.history(period=period, interval=interval)

    if df.empty:
        raise ValueError(f"No data found for ticker: {ticker}")

    interval_name = {"1wk": "weeks", "1d": "days", "1mo": "months"}.get(interval, "bars")
    print(f"[OK] Downloaded {len(df)} {interval_name} of data")
    return df


def calculate_moving_averages(df: pd.DataFrame, short_window: int = 10, long_window: int = 40) -> pd.DataFrame:
    """
    이동평균선 계산

    주봉 차트: 10주, 40주 이동평균 (William O'Neil의 핵심 지표)
    일봉 차트: 50일, 200일 이동평균

    Args:
        df: OHLCV 데이터프레임
        short_window: 단기 이동평균 기간 (주봉: 10, 일봉: 50)
        long_window: 장기 이동평균 기간 (주봉: 40, 일봉: 200)

    Returns:
        이동평균선이 추가된 데이터프레임
    """
    df[f'MA{short_window}'] = df['Close'].rolling(window=short_window).mean()
    df[f'MA{long_window}'] = df['Close'].rolling(window=long_window).mean()
    # 호환성을 위해 기존 컬럼명도 유지
    df['MA50'] = df[f'MA{short_window}']
    df['MA200'] = df[f'MA{long_window}']
    return df
