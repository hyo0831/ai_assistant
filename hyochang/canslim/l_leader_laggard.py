"""
L - Leader or Laggard

RS Rating은 pattern_detector.py에서 이미 계산됨.
여기서는 추가 리더/래거드 판단 근거를 수집.
"""

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


def analyze(info: dict, rs_analysis: dict = None) -> Dict:
    """리더/래거드 판단 근거 수집"""
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

        # RS 분석 결과 통합 (pattern_detector에서 제공)
        if rs_analysis:
            result['rs_rating'] = rs_analysis.get('rs_rating')
            result['rs_trend'] = rs_analysis.get('rs_trend')
            result['rs_new_high'] = rs_analysis.get('rs_new_high')
            result['rs_vs_benchmark'] = rs_analysis.get('rs_vs_benchmark', rs_analysis.get('rs_vs_sp500', {}))
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
    rs = data.get('rs_rating')
    if rs is not None:
        if rs >= 85:
            lines.append(f"RS Rating (vs {bm}): {rs}/99 (LEADER - O'Neil buy zone 85+)")
        elif rs >= 70:
            lines.append(f"RS Rating (vs {bm}): {rs}/99 (above average)")
        else:
            lines.append(f"RS Rating (vs {bm}): {rs}/99 (LAGGARD - O'Neil: never buy below 70)")
    if data.get('rs_trend'):
        lines.append(f"RS Trend (10-week): {data['rs_trend']}")
    if data.get('rs_new_high') is not None:
        lines.append(f"RS New High: {'Yes - BULLISH signal' if data['rs_new_high'] else 'No'}")

    # 기간별 성과 (단기→장기 순서로 표시)
    rs_data = data.get('rs_vs_benchmark', {})
    period_order = ['3M', '6M', '1Y', '2Y', '3Y']
    sorted_periods = sorted(rs_data.keys(), key=lambda x: period_order.index(x) if x in period_order else 99)
    if sorted_periods:
        lines.append(f"Performance vs {bm} (short→long term):")
        for period in sorted_periods:
            vals = rs_data[period]
            bm_ret = vals.get('benchmark_return', vals.get('sp500_return', 0))
            out = vals['outperformance']
            flag = " [OUTPERFORM]" if out > 0 else " [UNDERPERFORM]"
            lines.append(f"  {period}: Stock {vals['stock_return']:+.1f}% vs {bm} {bm_ret:+.1f}% (Outperformance: {out:+.1f}%){flag}")

    if data.get('data_note'):
        lines.append(f"Note: {data['data_note']}")

    lines.append("")
    lines.append(ONEIL_RULE)

    return "\n".join(lines)
