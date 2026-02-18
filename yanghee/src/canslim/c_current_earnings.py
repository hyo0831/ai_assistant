"""
C - Current Quarterly Earnings per Share

O'Neil 기준:
- 최근 분기 EPS가 전년 동기 대비 25-50%+ 성장
- 이상적: 40-500%+ ("The higher, the better")
- EPS 성장 가속(acceleration)이 핵심
- 매출 성장 25%+가 EPS 성장을 뒷받침해야 함
"""

import pandas as pd
from typing import Dict
from src.utils import find_financial_row, format_large_number, NET_INCOME_NAMES, REVENUE_NAMES

ONEIL_RULE = """
### C — Current Quarterly Earnings per Share (O'Neil 원문 규칙)
- Minimum requirement: Current quarterly EPS up at least 25-50% vs. same quarter prior year
- Ideal: EPS up 40% to 500% or more — "The higher, the better"
- 3 out of 4 of the greatest winners showed earnings increases averaging more than 70% in the latest quarter
- Earnings acceleration is critical: Look for the rate of growth to be speeding up in recent quarters
- Two consecutive quarters of major deceleration is a warning (decline of 2/3 or greater from previous rate)
- Sales growth of at least 25% must support earnings growth
- If both sales AND earnings have accelerated for the last three quarters, that is exceptionally bullish
""".strip()


def analyze(stock, info: dict) -> Dict:
    """최근 5개 분기 EPS YoY 성장률 데이터 수집"""
    result = {
        'quarterly_eps_growth_yoy': [],
        'quarterly_revenue': [],
        'quarterly_net_income': [],
        'revenue_growth': None,
        'eps_acceleration': None,
        'data_note': ''
    }

    try:
        quarterly = stock.quarterly_financials
        if quarterly is None or quarterly.empty:
            result['data_note'] = 'Quarterly financial data unavailable'
            return result

        ni_series = find_financial_row(quarterly, NET_INCOME_NAMES)
        if ni_series is not None:
            for i in range(min(8, len(ni_series))):
                date_label = ni_series.index[i].strftime('%Y-%m') if hasattr(ni_series.index[i], 'strftime') else str(ni_series.index[i])
                result['quarterly_net_income'].append({
                    'period': date_label,
                    'net_income': round(float(ni_series.iloc[i]), 0)
                })

            num_quarters = min(5, len(ni_series) - 4)
            for i in range(max(0, num_quarters)):
                recent_q = ni_series.iloc[i]
                year_ago_q = ni_series.iloc[i + 4]
                if pd.isna(recent_q) or pd.isna(year_ago_q) or year_ago_q == 0:
                    result['quarterly_eps_growth_yoy'].append(None)
                    continue
                yoy = ((recent_q - year_ago_q) / abs(year_ago_q)) * 100
                yoy = max(-999, min(9999, yoy))
                result['quarterly_eps_growth_yoy'].append(round(float(yoy), 1))

            growths = [g for g in result['quarterly_eps_growth_yoy'] if g is not None]
            if len(growths) >= 3:
                if growths[0] > growths[1] > growths[2]:
                    result['eps_acceleration'] = 'ACCELERATING'
                elif growths[0] < growths[1] < growths[2]:
                    result['eps_acceleration'] = 'DECELERATING'
                elif len(growths) >= 2 and growths[1] != 0 and growths[0] < growths[1] * 0.33:
                    result['eps_acceleration'] = 'SHARP DECELERATION WARNING'
                else:
                    result['eps_acceleration'] = 'MIXED'
        else:
            result['data_note'] = 'Net Income row not found in quarterly financials'

        rev_series = find_financial_row(quarterly, REVENUE_NAMES)
        if rev_series is not None:
            for i in range(min(8, len(rev_series))):
                date_label = rev_series.index[i].strftime('%Y-%m') if hasattr(rev_series.index[i], 'strftime') else str(rev_series.index[i])
                result['quarterly_revenue'].append({
                    'period': date_label,
                    'revenue': round(float(rev_series.iloc[i]), 0)
                })

        rev_growth = info.get('revenueGrowth')
        if rev_growth is not None:
            result['revenue_growth'] = round(float(rev_growth * 100), 1)

    except Exception as e:
        result['data_note'] = f'Error collecting quarterly data: {e}'

    return result


def format_for_prompt(data: Dict, currency: str = 'USD') -> str:
    """AI 프롬프트에 삽입할 텍스트 생성"""
    lines = ["### C - Current Quarterly Earnings"]

    yoy = data.get('quarterly_eps_growth_yoy', [])
    if yoy:
        lines.append(f"Recent {len(yoy)}Q YoY EPS growth rates: {yoy}")
        latest = yoy[0] if yoy[0] is not None else 'N/A'
        lines.append(f"Latest quarter YoY: {latest}%")
        lines.append(f"O'Neil minimum: 25-50%+, ideal 40-500%+")

    if data.get('eps_acceleration'):
        lines.append(f"Acceleration status: {data['eps_acceleration']}")

    ni = data.get('quarterly_net_income', [])
    if ni:
        ni_text = ", ".join([f"{q['period']}: {format_large_number(q['net_income'], currency)}" for q in ni[:6]])
        lines.append(f"Net Income trend ({currency}): {ni_text}")

    rev = data.get('quarterly_revenue', [])
    if rev:
        rev_text = ", ".join([f"{q['period']}: {format_large_number(q['revenue'], currency)}" for q in rev[:6]])
        lines.append(f"Revenue trend ({currency}): {rev_text}")

    if data.get('revenue_growth') is not None:
        lines.append(f"Revenue growth: {data['revenue_growth']:+.1f}%")

    if data.get('data_note'):
        lines.append(f"Note: {data['data_note']}")

    lines.append("")
    lines.append(ONEIL_RULE)
    return "\n".join(lines)
