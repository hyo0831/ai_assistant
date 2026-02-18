"""
L - Leader or Laggard

RS Rating을 자체 계산하여 리더/래거드 판단 근거 수집.
(hyochang에서는 pattern_detector.py에서 RS Rating을 받아썼으나,
 분석 모드에서는 차트 패턴 감지 없이 독립적으로 RS를 계산)
"""

import numpy as np
import pandas as pd
import yfinance as yf
from typing import Dict

ONEIL_RULE = """
### L — Leader or Laggard (O'Neil 원문 규칙)
- Buy the #1 company in its field — the one with the best quarterly and annual earnings growth,
  highest ROE, widest profit margins, strongest sales growth, and most dynamic stock price action
- Do NOT buy "sympathy plays" — they never perform as well as the real leader
- Relative Price Strength (RS) Rating of 85 or higher is required — average RS of best stocks was 87
- Never buy stocks with RS Ratings in the 40s, 50s, or 60s
- During market corrections, the best growth stocks decline 1.5 to 2.5 times the market average
- The stocks that decline the LEAST during corrections are usually the best future selections
- Always sell your worst performers first and keep your best longer
""".strip()


def _get_benchmark_for_ticker(ticker: str) -> tuple:
    """종목 코드에 따라 적절한 벤치마크 지수 반환"""
    ticker_upper = ticker.upper()
    if ticker_upper.endswith('.KS'):
        return ('^KS11', 'KOSPI')
    elif ticker_upper.endswith('.KQ'):
        return ('^KQ11', 'KOSDAQ')
    elif ticker_upper.endswith('.T'):
        return ('^N225', 'Nikkei 225')
    else:
        return ('^GSPC', 'S&P 500')


def _compute_rs_rating(stock, ticker: str) -> Dict:
    """
    오닐 스타일 상대강도(RS) 분석
    - 4분기 가중 공식 (40/20/20/20)으로 RS Rating 1-99 산출
    - RS 추세 (RISING/FALLING/FLAT) 및 RS 신고가 판단
    """
    benchmark_ticker, benchmark_name = _get_benchmark_for_ticker(ticker)

    result = {
        'benchmark': benchmark_name,
        'rs_vs_benchmark': {},
        'rs_rating': None,
        'rs_trend': 'N/A',
        'rs_new_high': False,
        'interpretation': ''
    }

    try:
        # 종목 주봉 데이터
        df = stock.history(period="3y", interval="1wk")
        if df is None or df.empty or len(df) < 13:
            result['interpretation'] = 'Insufficient price data for RS calculation'
            return result

        # 벤치마크 데이터 다운로드
        start_date = df.index[0].strftime('%Y-%m-%d')
        end_date = df.index[-1].strftime('%Y-%m-%d')

        print(f"    (Benchmark: {benchmark_name} [{benchmark_ticker}])")
        benchmark = yf.Ticker(benchmark_ticker)
        sp_df = benchmark.history(start=start_date, end=end_date, interval="1wk")

        if sp_df.empty or len(sp_df) < 13:
            result['interpretation'] = f'{benchmark_name} data unavailable for RS calculation'
            return result

        # 날짜 인덱스 tz-naive 통일
        stock_idx = df.index.tz_localize(None) if df.index.tz is not None else df.index
        sp_idx = sp_df.index.tz_localize(None) if sp_df.index.tz is not None else sp_df.index

        stock_series = pd.Series(df['Close'].values, index=stock_idx).sort_index()
        sp_series = pd.Series(sp_df['Close'].values, index=sp_idx).sort_index()

        # 공통 날짜 매칭
        common_idx = stock_series.index.intersection(sp_series.index)
        if len(common_idx) < 13:
            stock_closes = stock_series
            sp_closes = sp_series
        else:
            stock_closes = stock_series.loc[common_idx]
            sp_closes = sp_series.loc[common_idx]

        # 기간별 수익률 계산
        periods = {'13w': 13, '26w': 26, '52w': 52}
        for label, weeks in periods.items():
            if len(stock_closes) > weeks and len(sp_closes) > weeks:
                stock_return = ((stock_closes.iloc[-1] - stock_closes.iloc[-weeks]) / stock_closes.iloc[-weeks]) * 100
                sp_return = ((sp_closes.iloc[-1] - sp_closes.iloc[-weeks]) / sp_closes.iloc[-weeks]) * 100
                outperformance = stock_return - sp_return
                result['rs_vs_benchmark'][label] = {
                    'stock_return': round(float(stock_return), 1),
                    'benchmark_return': round(float(sp_return), 1),
                    'outperformance': round(float(outperformance), 1)
                }

        # RS Rating (오닐 가중치: 최근 분기 40%, 나머지 각 20%)
        if len(stock_closes) >= 52 and len(sp_closes) >= 52:
            q1 = ((stock_closes.iloc[-1] - stock_closes.iloc[-13]) / stock_closes.iloc[-13]) * 100
            q2 = ((stock_closes.iloc[-13] - stock_closes.iloc[-26]) / stock_closes.iloc[-26]) * 100 if len(stock_closes) > 26 else 0
            q3 = ((stock_closes.iloc[-26] - stock_closes.iloc[-39]) / stock_closes.iloc[-39]) * 100 if len(stock_closes) > 39 else 0
            q4 = ((stock_closes.iloc[-39] - stock_closes.iloc[-52]) / stock_closes.iloc[-52]) * 100 if len(stock_closes) > 52 else 0

            sp_q1 = ((sp_closes.iloc[-1] - sp_closes.iloc[-13]) / sp_closes.iloc[-13]) * 100
            sp_q2 = ((sp_closes.iloc[-13] - sp_closes.iloc[-26]) / sp_closes.iloc[-26]) * 100 if len(sp_closes) > 26 else 0
            sp_q3 = ((sp_closes.iloc[-26] - sp_closes.iloc[-39]) / sp_closes.iloc[-39]) * 100 if len(sp_closes) > 39 else 0
            sp_q4 = ((sp_closes.iloc[-39] - sp_closes.iloc[-52]) / sp_closes.iloc[-52]) * 100 if len(sp_closes) > 52 else 0

            weighted_stock = q1 * 0.4 + q2 * 0.2 + q3 * 0.2 + q4 * 0.2
            weighted_sp = sp_q1 * 0.4 + sp_q2 * 0.2 + sp_q3 * 0.2 + sp_q4 * 0.2

            relative_perf = weighted_stock - weighted_sp
            rs_rating = int(min(99, max(1, 50 + relative_perf * 1.0)))
            result['rs_rating'] = rs_rating

        # RS 추세 (최근 10주 RS Line 방향)
        if len(stock_closes) >= 10 and len(sp_closes) >= 10:
            common_len = min(len(stock_closes), len(sp_closes))
            rs_line = stock_closes.iloc[-common_len:].values / sp_closes.iloc[-common_len:].values

            rs_recent = rs_line[-5:].mean()
            rs_prior = rs_line[-10:-5].mean()

            if rs_recent > rs_prior * 1.02:
                result['rs_trend'] = 'RISING'
            elif rs_recent < rs_prior * 0.98:
                result['rs_trend'] = 'FALLING'
            else:
                result['rs_trend'] = 'FLAT'

            # RS 신고가 체크
            if len(rs_line) >= 52:
                rs_52w_high = np.max(rs_line[-52:])
                if rs_line[-1] >= rs_52w_high * 0.98:
                    result['rs_new_high'] = True

        # 해석
        rs = result['rs_rating']
        if rs is not None:
            bm = benchmark_name
            if rs >= 85:
                result['interpretation'] = f"STRONG LEADER (RS {rs} vs {bm}): Stock significantly outperforms the market. O'Neil says buy only RS 85+."
            elif rs >= 70:
                result['interpretation'] = f"ABOVE AVERAGE (RS {rs} vs {bm}): Outperforming market but not in top tier. Watch for improvement."
            elif rs >= 50:
                result['interpretation'] = f"AVERAGE (RS {rs} vs {bm}): Performing roughly in line with market. Not a leader."
            else:
                result['interpretation'] = f"LAGGARD (RS {rs} vs {bm}): Underperforming the market. O'Neil says never buy RS below 70."

    except Exception as e:
        result['interpretation'] = f'RS calculation error: {str(e)}'

    return result


def analyze(stock, info: dict, ticker: str) -> Dict:
    """리더/래거드 판단 근거 수집 + RS Rating 자체 계산"""
    result = {
        'sector': None,
        'industry': None,
        'rs_rating': None,
        'rs_trend': None,
        'rs_new_high': None,
        'rs_vs_benchmark': {},
        'benchmark': None,
        'data_note': ''
    }

    try:
        result['sector'] = info.get('sector')
        result['industry'] = info.get('industry')

        # RS Rating 자체 계산
        rs_analysis = _compute_rs_rating(stock, ticker)
        result['rs_rating'] = rs_analysis.get('rs_rating')
        result['rs_trend'] = rs_analysis.get('rs_trend')
        result['rs_new_high'] = rs_analysis.get('rs_new_high')
        result['rs_vs_benchmark'] = rs_analysis.get('rs_vs_benchmark', {})
        result['benchmark'] = rs_analysis.get('benchmark', 'S&P 500')

    except Exception as e:
        result['data_note'] = f'Error: {e}'

    return result


def format_for_prompt(data: Dict) -> str:
    """AI 프롬프트에 삽입할 텍스트 생성"""
    lines = ["### L - Leader or Laggard"]

    if data.get('sector'):
        lines.append(f"Sector: {data['sector']}")
    if data.get('industry'):
        lines.append(f"Industry: {data['industry']}")

    bm = data.get('benchmark', 'Market')
    if data.get('rs_rating') is not None:
        lines.append(f"RS Rating (vs {bm}): {data['rs_rating']}/99")
    if data.get('rs_trend'):
        lines.append(f"RS Trend (10-week): {data['rs_trend']}")
    if data.get('rs_new_high') is not None:
        lines.append(f"RS New High: {'Yes' if data['rs_new_high'] else 'No'}")

    rs_data = data.get('rs_vs_benchmark', {})
    for period, vals in rs_data.items():
        bm_ret = vals.get('benchmark_return', 0)
        lines.append(f"  {period}: Stock {vals['stock_return']:+.1f}% vs {bm} {bm_ret:+.1f}% (Outperformance: {vals['outperformance']:+.1f}%)")

    if data.get('data_note'):
        lines.append(f"Note: {data['data_note']}")

    lines.append("")
    lines.append(ONEIL_RULE)

    return "\n".join(lines)
