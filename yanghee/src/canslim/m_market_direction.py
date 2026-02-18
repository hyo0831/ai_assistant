"""
M - Market Direction

O'Neil: "투자의 50%는 시장 방향"
S&P 500, NASDAQ + 한국 KOSPI/KOSDAQ 지수의 추세 및 Distribution Day 데이터 수집.
"""

import pandas as pd
import yfinance as yf
from typing import Dict
from src.utils import is_korean_stock

ONEIL_RULE = """
### M — Market Direction (O'Neil 원문 규칙)
- This is 50% of the entire investing game
- You can be right on every other factor, but if the market turns down, 3 out of 4 stocks will fall
- Follow the daily S&P 500, Nasdaq Composite, Dow Jones, NYSE Composite charts
- Never rely on personal opinions — observe the actual market indexes

Detecting Market Tops (Distribution):
- Look for 3-5 "distribution days" within a 4-5 week period
- Distribution day = index closes down 0.2%+ on higher volume than prior day
- Also watch for "stalling" = heavy volume without further upside progress
- When distribution is confirmed, sell immediately — put at least 25% in cash

Detecting Market Bottoms (Follow-Through):
- Wait for a "follow-through day" starting on the 4th day of a rally attempt
- Follow-through = major average advances 1.5%+ on volume higher than prior day
- Not all follow-throughs succeed
- Buy gradually, starting with smaller positions

Bear Market Rules:
- Bear markets typically have 3 legs of decline with convincing-looking rallies between
- A 33% loss requires 50% gain to break even; 50% loss requires 100%
""".strip()


def analyze(ticker: str = '') -> Dict:
    """시장 방향 데이터 수집"""
    result = {
        'sp500': _analyze_index('^GSPC', 'S&P 500'),
        'nasdaq': _analyze_index('^IXIC', 'NASDAQ'),
        'data_note': ''
    }

    # 한국 주식이면 KOSPI/KOSDAQ도 분석
    if is_korean_stock(ticker):
        result['kospi'] = _analyze_index('^KS11', 'KOSPI')
        result['kosdaq'] = _analyze_index('^KQ11', 'KOSDAQ')

    return result


def _analyze_index(ticker: str, name: str) -> Dict:
    """개별 지수 분석 데이터"""
    data = {
        'name': name,
        'current_price': None,
        'vs_50dma': None,
        'vs_200dma': None,
        'trend': 'N/A',
        'distribution_days_5wk': 0,
        'recent_distribution': [],
    }

    try:
        idx = yf.Ticker(ticker)
        df = idx.history(period="3mo", interval="1d")

        if df is None or df.empty or len(df) < 20:
            return data

        closes = df['Close'].values
        volumes = df['Volume'].values
        dates = df.index
        current = closes[-1]
        data['current_price'] = round(float(current), 2)

        # 이동평균 대비
        if len(closes) >= 50:
            ma50 = pd.Series(closes).rolling(50).mean().iloc[-1]
            if not pd.isna(ma50) and ma50 > 0:
                data['vs_50dma'] = round(((current - ma50) / ma50) * 100, 1)

        if len(closes) >= 60:
            try:
                df_long = idx.history(period="1y", interval="1d")
                if len(df_long) >= 200:
                    ma200 = df_long['Close'].rolling(200).mean().iloc[-1]
                    if not pd.isna(ma200) and ma200 > 0:
                        data['vs_200dma'] = round(((current - ma200) / ma200) * 100, 1)
            except Exception:
                pass

        # 추세 판단
        if data['vs_50dma'] is not None:
            if data['vs_50dma'] > 2:
                data['trend'] = 'UPTREND'
            elif data['vs_50dma'] < -2:
                data['trend'] = 'DOWNTREND'
            else:
                data['trend'] = 'SIDEWAYS'

        # Distribution Day 카운트 (최근 25거래일)
        dist_count = 0
        lookback = min(25, len(df) - 1)
        for i in range(len(df) - lookback, len(df)):
            if i < 1:
                continue
            daily_change = (closes[i] - closes[i-1]) / closes[i-1]
            if daily_change <= -0.002 and volumes[i] > volumes[i-1]:
                dist_count += 1
                date_str = dates[i].strftime('%Y-%m-%d') if hasattr(dates[i], 'strftime') else str(dates[i])
                data['recent_distribution'].append({
                    'date': date_str,
                    'change': round(float(daily_change * 100), 2)
                })
        data['distribution_days_5wk'] = dist_count

    except Exception:
        pass

    return data


def format_for_prompt(data: Dict) -> str:
    """AI 프롬프트에 삽입할 텍스트 생성"""
    lines = ["### M - Market Direction"]

    # 모든 지수 키를 순회 (sp500, nasdaq + 한국 kospi, kosdaq)
    index_keys = ['sp500', 'nasdaq', 'kospi', 'kosdaq']
    for key in index_keys:
        if key not in data:
            continue
        idx = data[key]
        name = idx.get('name', key)
        lines.append(f"\n**{name}:**")

        if idx.get('current_price'):
            lines.append(f"  Current: {idx['current_price']:,.2f}")
        if idx.get('vs_50dma') is not None:
            lines.append(f"  vs 50-DMA: {idx['vs_50dma']:+.1f}%")
        if idx.get('vs_200dma') is not None:
            lines.append(f"  vs 200-DMA: {idx['vs_200dma']:+.1f}%")
        if idx.get('trend') != 'N/A':
            lines.append(f"  Trend: {idx['trend']}")
        lines.append(f"  Distribution Days (5wk): {idx.get('distribution_days_5wk', 0)}")

        dist_list = idx.get('recent_distribution', [])
        if dist_list:
            recent_3 = dist_list[-3:]
            for d in recent_3:
                lines.append(f"    {d['date']}: {d['change']:+.2f}%")

    # 종합 경고
    max_dist = 0
    for key in index_keys:
        if key in data:
            max_dist = max(max_dist, data[key].get('distribution_days_5wk', 0))

    if max_dist >= 5:
        lines.append("\nWARNING: 5+ distribution days detected - O'Neil says this is a market top signal")
    elif max_dist >= 3:
        lines.append("\nCAUTION: Distribution days accumulating - watch closely")

    if data.get('data_note'):
        lines.append(f"\nNote: {data['data_note']}")

    lines.append("")
    lines.append(ONEIL_RULE)

    return "\n".join(lines)
