"""
A - Annual Earnings Increases

데이터 수집 후 AI가 판단할 수 있도록 근거 제공에 집중.
O'Neil 원문 규칙은 RAG로 프롬프트에 포함.
"""

import pandas as pd
from typing import Dict

# O'Neil 원문 (william_oneil_system_prompt.md에서 발췌) - RAG 참조용
ONEIL_RULE = """
### A — Annual Earnings Increases (O'Neil 원문 규칙)
- Require annual EPS growth in each of the last 3 years (ideally 5 years)
- Minimum annual growth rate: 25% — ideally 50% or even 100%+
- The median annual growth rate of outstanding stocks in our study at their early stage was 36%
- A typical EPS progression: $0.70, $1.15, $1.85, $2.65, $4.00
- You normally don't want the second year's earnings to be down
- One down year in five years is acceptable only if the following year rebounds to new highs
- Return on Equity (ROE) must be at least 17% — superior growth stocks show 25% to 50% ROE
- Cash flow per share should be at least 20% greater than actual EPS
- For turnaround stocks: Look for at least 5-10% annual earnings growth and two straight quarters of sharp recovery
""".strip()


def analyze(stock, info: dict) -> Dict:
    """최근 5년 연간 실적 데이터 수집"""
    result = {
        'annual_net_income': [],      # 연도별 순이익
        'annual_growth_rates': [],    # YoY 성장률
        'consecutive_growth_years': 0,
        'roe': None,
        'pe_ratio': None,
        'forward_pe': None,
        'profit_margins': None,
        'data_note': ''
    }

    try:
        annual = stock.financials
        if annual is not None and not annual.empty and 'Net Income' in annual.index:
            ni_series = annual.loc['Net Income'].dropna()
            num_years = min(5, len(ni_series))

            for i in range(num_years):
                date_label = ni_series.index[i].strftime('%Y') if hasattr(ni_series.index[i], 'strftime') else str(ni_series.index[i])
                result['annual_net_income'].append({
                    'year': date_label,
                    'net_income': round(float(ni_series.iloc[i]), 0)
                })

            # YoY 성장률
            for i in range(num_years - 1):
                curr = ni_series.iloc[i]
                prev = ni_series.iloc[i + 1]
                if pd.isna(curr) or pd.isna(prev) or prev == 0:
                    result['annual_growth_rates'].append(None)
                    continue
                yoy = ((curr - prev) / abs(prev)) * 100
                result['annual_growth_rates'].append(round(float(yoy), 1))

            # 연속 성장 연수
            for i in range(num_years - 1):
                if ni_series.iloc[i] > ni_series.iloc[i + 1]:
                    result['consecutive_growth_years'] += 1
                else:
                    break

        # ROE, P/E, Margins
        roe = info.get('returnOnEquity')
        if roe is not None:
            result['roe'] = round(float(roe * 100), 1)

        pe = info.get('trailingPE')
        if pe is not None:
            result['pe_ratio'] = round(float(pe), 1)

        fpe = info.get('forwardPE')
        if fpe is not None:
            result['forward_pe'] = round(float(fpe), 1)

        margins = info.get('profitMargins')
        if margins is not None:
            result['profit_margins'] = round(float(margins * 100), 1)

    except Exception as e:
        result['data_note'] = f'Error: {e}'

    return result


def format_for_prompt(data: Dict) -> str:
    """AI 프롬프트에 삽입할 텍스트 생성 (RAG 규칙 포함)"""
    lines = ["### A - Annual Earnings Increases"]

    # 데이터
    ni = data.get('annual_net_income', [])
    if ni:
        ni_text = ", ".join([f"{y['year']}: {y['net_income']:,.0f}" for y in ni])
        lines.append(f"Annual Net Income ({len(ni)}Y): {ni_text}")

    rates = data.get('annual_growth_rates', [])
    if rates:
        lines.append(f"YoY growth rates: {rates}")

    consec = data.get('consecutive_growth_years', 0)
    lines.append(f"Consecutive growth years (from latest): {consec}")

    if data.get('roe') is not None:
        lines.append(f"ROE: {data['roe']}%")
    if data.get('pe_ratio') is not None:
        lines.append(f"Trailing P/E: {data['pe_ratio']}")
    if data.get('forward_pe') is not None:
        lines.append(f"Forward P/E: {data['forward_pe']}")
    if data.get('profit_margins') is not None:
        lines.append(f"Profit Margins: {data['profit_margins']}%")
    if data.get('data_note'):
        lines.append(f"Note: {data['data_note']}")

    # RAG: O'Neil 규칙 원문
    lines.append("")
    lines.append(ONEIL_RULE)

    return "\n".join(lines)
