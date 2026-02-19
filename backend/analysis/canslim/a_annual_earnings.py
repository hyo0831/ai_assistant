"""
A - Annual Earnings Increases
"""

import pandas as pd
from typing import Dict
from analysis.utils import find_financial_row, format_large_number, NET_INCOME_NAMES

ONEIL_RULE = """
### A — Annual Earnings Increases (O'Neil 원문 규칙)
- Require annual EPS growth in each of the last 3 years (ideally 5 years)
- Minimum annual growth rate: 25% — ideally 50% or even 100%+
- The median annual growth rate of outstanding stocks in our study at their early stage was 36%
- You normally don't want the second year's earnings to be down
- One down year in five years is acceptable only if the following year rebounds to new highs
- Return on Equity (ROE) must be at least 17% — superior growth stocks show 25% to 50% ROE
""".strip()


def analyze(stock, info: dict) -> Dict:
    """최근 5년 연간 실적 데이터 수집"""
    result = {
        'annual_net_income': [],
        'annual_growth_rates': [],
        'consecutive_growth_years': 0,
        'roe': None,
        'pe_ratio': None,
        'forward_pe': None,
        'profit_margins': None,
        'data_note': ''
    }

    try:
        annual = stock.financials
        ni_series = find_financial_row(annual, NET_INCOME_NAMES) if annual is not None else None

        if ni_series is not None:
            num_years = min(5, len(ni_series))
            for i in range(num_years):
                date_label = ni_series.index[i].strftime('%Y') if hasattr(ni_series.index[i], 'strftime') else str(ni_series.index[i])
                result['annual_net_income'].append({
                    'year': date_label,
                    'net_income': round(float(ni_series.iloc[i]), 0)
                })

            for i in range(num_years - 1):
                curr = ni_series.iloc[i]
                prev = ni_series.iloc[i + 1]
                if pd.isna(curr) or pd.isna(prev) or prev == 0:
                    result['annual_growth_rates'].append(None)
                    continue
                yoy = ((curr - prev) / abs(prev)) * 100
                result['annual_growth_rates'].append(round(float(yoy), 1))

            for i in range(num_years - 1):
                if ni_series.iloc[i] > ni_series.iloc[i + 1]:
                    result['consecutive_growth_years'] += 1
                else:
                    break
        else:
            result['data_note'] = 'Annual Net Income data unavailable'

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


def format_for_prompt(data: Dict, currency: str = 'USD') -> str:
    lines = ["### A - Annual Earnings Increases"]

    ni = data.get('annual_net_income', [])
    if ni:
        ni_text = ", ".join([f"{y['year']}: {format_large_number(y['net_income'], currency)}" for y in ni])
        lines.append(f"Annual Net Income ({len(ni)}Y, {currency}): {ni_text}")

    rates = data.get('annual_growth_rates', [])
    if rates:
        lines.append(f"YoY growth rates: {rates}")
    lines.append(f"Consecutive growth years (from latest): {data.get('consecutive_growth_years', 0)}")

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

    lines.append("")
    lines.append(ONEIL_RULE)
    return "\n".join(lines)
