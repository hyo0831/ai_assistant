"""
I - Institutional Sponsorship

기관 보유 현황 데이터 수집. AI가 판단할 근거 제공.
"""

from typing import Dict
from src.utils import is_korean_stock

ONEIL_RULE = """
### I — Institutional Sponsorship (O'Neil 원문 규칙)
- A stock needs at least several institutional sponsors (20 minimum for small/newer companies)
- More important than quantity is QUALITY — look for stocks owned by the better-performing mutual funds
- Look for increasing number of institutional owners over recent quarters
- New positions taken in the most recent quarter are more relevant than old holdings
- Beware of "overowned" stocks — excessive institutional ownership creates potential for massive selling
- If no better-performing funds own the stock, pass on it
""".strip()


def analyze(stock, info: dict, ticker: str = '') -> Dict:
    """기관 보유 현황 데이터 수집"""
    result = {
        'inst_holders_pct': None,
        'inst_holders_count': None,
        'top_holders': [],
        'data_note': ''
    }

    # 한국 주식은 yfinance에서 기관 보유 데이터가 제한적
    if is_korean_stock(ticker):
        result['data_note'] = '한국 주식은 yfinance 기관 보유 데이터가 제한적입니다. 금융감독원 전자공시(DART) 등 별도 확인 필요.'

    try:
        inst_pct = info.get('heldPercentInstitutions')
        if inst_pct is not None:
            result['inst_holders_pct'] = round(float(inst_pct * 100), 1)

        try:
            inst_holders = stock.institutional_holders
            if inst_holders is not None and not inst_holders.empty:
                result['inst_holders_count'] = len(inst_holders)
                if 'Holder' in inst_holders.columns:
                    holders_data = []
                    for _, row in inst_holders.head(10).iterrows():
                        holder_info = {'name': row.get('Holder', 'Unknown')}
                        if 'Shares' in row and row['Shares']:
                            holder_info['shares'] = int(row['Shares'])
                        if 'Value' in row and row['Value']:
                            holder_info['value'] = int(row['Value'])
                        holders_data.append(holder_info)
                    result['top_holders'] = holders_data
        except Exception:
            pass

    except Exception as e:
        result['data_note'] += f' Error: {e}' if result['data_note'] else f'Error: {e}'

    return result


def format_for_prompt(data: Dict) -> str:
    """AI 프롬프트에 삽입할 텍스트 생성"""
    lines = ["### I - Institutional Sponsorship"]

    if data.get('inst_holders_pct') is not None:
        lines.append(f"Institutional Ownership: {data['inst_holders_pct']}%")
    if data.get('inst_holders_count') is not None:
        lines.append(f"Number of Institutional Holders: {data['inst_holders_count']}")

    holders = data.get('top_holders', [])
    if holders:
        lines.append("Top Institutional Holders:")
        for h in holders:
            shares_str = f" ({h['shares']:,} shares)" if 'shares' in h else ""
            lines.append(f"  - {h['name']}{shares_str}")

    if data.get('data_note'):
        lines.append(f"Note: {data['data_note']}")

    lines.append("")
    lines.append(ONEIL_RULE)

    return "\n".join(lines)
