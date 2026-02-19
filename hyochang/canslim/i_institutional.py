"""
I - Institutional Sponsorship

기관 보유 현황 데이터 수집. AI가 판단할 근거 제공.
"""

from typing import Dict

ONEIL_RULE = """
### I — Institutional Sponsorship (O'Neil 원문 규칙)
- A stock needs at least several institutional sponsors (20 minimum for small/newer companies)
- More important than quantity is QUALITY — look for stocks owned by the better-performing mutual funds
- Look for increasing number of institutional owners over recent quarters
- New positions taken in the most recent quarter are more relevant than old holdings
- Beware of "overowned" stocks — excessive institutional ownership creates potential for massive selling
- If no better-performing funds own the stock, pass on it
""".strip()


def analyze(stock, info: dict) -> Dict:
    """기관 보유 현황 데이터 수집"""
    result = {
        'inst_holders_pct': None,
        'inst_holders_count': None,
        'top_holders': [],
        'data_note': ''
    }

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
        result['data_note'] = f'Error: {e}'

    return result


def format_for_prompt(data: Dict) -> str:
    """AI 프롬프트에 삽입할 텍스트 생성"""
    lines = ["### I - Institutional Sponsorship"]

    if data.get('inst_holders_pct') is not None:
        pct = data['inst_holders_pct']
        if pct >= 70:
            lines.append(f"Institutional Ownership: {pct}% (WARNING: overowned - excessive selling risk)")
        elif pct >= 30:
            lines.append(f"Institutional Ownership: {pct}% (healthy institutional interest)")
        else:
            lines.append(f"Institutional Ownership: {pct}% (LOW - insufficient institutional support)")
    if data.get('inst_holders_count') is not None:
        count = data['inst_holders_count']
        if count >= 20:
            lines.append(f"Number of Institutional Holders: {count} (meets O'Neil minimum of 20+)")
        else:
            lines.append(f"Number of Institutional Holders: {count} (BELOW O'Neil minimum of 20)")

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
