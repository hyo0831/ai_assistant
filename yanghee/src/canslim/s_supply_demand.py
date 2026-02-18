"""
S - Supply and Demand

데이터 수집에 집중. 점수 없이 AI가 판단할 근거만 제공.
"""

import pandas as pd
from typing import Dict
from src.utils import format_large_number, get_market_cap_label, SHARE_COUNT_NAMES

ONEIL_RULE = """
### S — Supply and Demand (O'Neil 원문 규칙)
- Smaller-cap stocks (fewer shares outstanding) can move faster, but with greater risk on both sides
- Companies where top management owns a large percentage of stock (at least 1-3% in large companies, more in small) are preferred
- Stock buybacks are positive — a 10% buyback is considered significant
- Lower debt-to-equity ratio is generally better — highly leveraged companies carry substantially higher risk
- Volume is the key measure of supply and demand:
  - When stock pulls back: volume should dry up
  - When stock rallies: volume should rise
  - Breakout volume must be at least 40-50% above normal
- Excessive stock splits can hurt
""".strip()


def analyze(stock, info: dict) -> Dict:
    """수급 관련 데이터 수집"""
    result = {
        'market_cap': None,
        'market_cap_label': '',
        'shares_outstanding': None,
        'float_shares': None,
        'insider_pct': None,
        'debt_to_equity': None,
        'buyback_detected': False,
        'share_change_pct': None,
        'data_note': ''
    }

    try:
        # 시가총액
        mcap = info.get('marketCap')
        if mcap:
            result['market_cap'] = mcap

        # 주식수
        shares = info.get('sharesOutstanding')
        if shares:
            result['shares_outstanding'] = shares

        float_shares = info.get('floatShares')
        if float_shares:
            result['float_shares'] = float_shares

        # 내부자 지분율
        insider_pct = info.get('heldPercentInsiders')
        if insider_pct is not None:
            result['insider_pct'] = round(float(insider_pct * 100), 1)

        # 부채비율
        dte = info.get('debtToEquity')
        if dte is not None:
            result['debt_to_equity'] = round(float(dte), 1)

        # 자사주 매입 여부 (발행주식수 변화로 추정)
        try:
            bs = stock.quarterly_balance_sheet
            if bs is not None and not bs.empty:
                shares_key = None
                for key in SHARE_COUNT_NAMES:
                    if key in bs.index:
                        shares_key = key
                        break
                if shares_key and bs.shape[1] >= 4:
                    recent = bs.loc[shares_key].iloc[0]
                    older = bs.loc[shares_key].iloc[3]
                    if not pd.isna(recent) and not pd.isna(older) and older > 0:
                        change_pct = ((recent - older) / older) * 100
                        result['share_change_pct'] = round(float(change_pct), 1)
                        if change_pct <= -2:
                            result['buyback_detected'] = True
        except Exception:
            pass

    except Exception as e:
        result['data_note'] = f'Error: {e}'

    return result


def format_for_prompt(data: Dict, currency: str = 'USD') -> str:
    """AI 프롬프트에 삽입할 텍스트 생성"""
    lines = ["### S - Supply and Demand"]

    mcap = data.get('market_cap')
    if mcap:
        label = get_market_cap_label(mcap, currency)
        cap_str = format_large_number(mcap, currency)
        data['market_cap_label'] = label
        lines.append(f"Market Cap: {label} ({cap_str})")

    if data.get('shares_outstanding'):
        lines.append(f"Shares Outstanding: {data['shares_outstanding']/1e6:.0f}M")
    if data.get('float_shares'):
        lines.append(f"Float Shares: {data['float_shares']/1e6:.0f}M")

    if data.get('insider_pct') is not None:
        lines.append(f"Insider Ownership: {data['insider_pct']}%")

    if data.get('debt_to_equity') is not None:
        lines.append(f"Debt-to-Equity: {data['debt_to_equity']}%")

    if data.get('share_change_pct') is not None:
        lines.append(f"Share count change (1yr): {data['share_change_pct']:+.1f}%")
    if data.get('buyback_detected'):
        lines.append("Buyback: Active share repurchase detected")

    if data.get('data_note'):
        lines.append(f"Note: {data['data_note']}")

    lines.append("")
    lines.append(ONEIL_RULE)

    return "\n".join(lines)
