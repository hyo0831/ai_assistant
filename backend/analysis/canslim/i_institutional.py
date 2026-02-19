"""
I - Institutional Sponsorship

기관 보유 현황 데이터 수집. AI가 판단할 근거 제공.
"""

from typing import Dict
from analysis.utils import is_korean_stock

ONEIL_RULE = """
### I — Institutional Sponsorship (O'Neil 원문 규칙)

[핵심 원칙]
- 기관이 전혀 없으면 전 세계 1만+ 기관이 분석 후 전부 패스한 것 — 강한 경고 신호
- 소형·신생 기업 기준 최소 20개 이상 기관 보유 필요
- 단순 보유 숫자보다 최근 분기 보유 기관 수 증가 추세가 더 중요
- 양(Quantity)보다 질(Quality) — IBD 등급 B+ 이상 성과 우수 펀드가 보유하는지 확인
- 최근 분기 신규 포지션 구축 기관에 주목 — 이후 수분기 지속 매수 가능성 높음
- 기관 매수·매도는 대형주 거래량의 70%까지 차지 — 주가 움직임의 실질적 원동력

[과잉보유(Overowned) 경계]
- 기관 보유가 지나치게 많으면 악재 한 번에 대량 매도 쓰나미 위험
- "모두가 담고 있다 = 추가 매수 여력 소진 = 수박의 심장이 이미 빠진 상태"
- 실제 사례: AIG(3,600개+ 기관) $100→$0.5 / Citigroup $57→$1 / Nokia·AOL 폭락

[분석 시 주의사항]
- 증권사 리서치·애널리스트 추천은 기관 후원이 아님 — 단기 noise에 불과
- 13F 공시는 분기 종료 후 약 6주 뒤 발표 — 실제 매수 시점과 최대 13주 차이 있음
- 성과 좋은 펀드 1개가 평범한 펀드 100개보다 의미 있음
- 패시브 ETF(Vanguard Index, iShares Core 등)는 종목 선택 의미 없음 — 액티브 펀드 위주로 판단
- 펀드 매니저 이직 시 과거 성과 등급이 새 매니저에게 그대로 적용되지 않음
""".strip()


def analyze(stock, info: dict, ticker: str = '') -> Dict:
    """기관 보유 현황 데이터 수집"""
    result = {
        'inst_holders_pct': None,
        'inst_holders_count': None,
        'mutual_fund_count': None,
        'top_holders': [],
        'top_mutual_funds': [],
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

        try:
            mf_holders = stock.mutualfund_holders
            if mf_holders is not None and not mf_holders.empty:
                result['mutual_fund_count'] = len(mf_holders)
                if 'Holder' in mf_holders.columns:
                    mf_data = []
                    for _, row in mf_holders.head(5).iterrows():
                        mf_info = {'name': row.get('Holder', 'Unknown')}
                        if 'Shares' in row and row['Shares']:
                            mf_info['shares'] = int(row['Shares'])
                        if 'Value' in row and row['Value']:
                            mf_info['value'] = int(row['Value'])
                        mf_data.append(mf_info)
                    result['top_mutual_funds'] = mf_data
        except Exception:
            pass

    except Exception as e:
        result['data_note'] += f' Error: {e}' if result['data_note'] else f'Error: {e}'

    return result


def format_for_prompt(data: Dict) -> str:
    """AI 프롬프트에 삽입할 텍스트 생성"""
    lines = ["### I - Institutional Sponsorship"]

    pct = data.get('inst_holders_pct')
    count = data.get('inst_holders_count')
    mf_count = data.get('mutual_fund_count')

    # 기관 보유 비율 해석
    if pct is not None:
        if pct >= 80:
            lines.append(f"Institutional Ownership: {pct}% — OVEROWNED 위험 구간 (악재 시 대량 매도 쓰나미 가능, AIG·Citigroup 유형)")
        elif pct >= 60:
            lines.append(f"Institutional Ownership: {pct}% — 높은 기관 관심, 과잉보유 여부 추가 확인 필요")
        elif pct >= 30:
            lines.append(f"Institutional Ownership: {pct}% — 건강한 기관 관심 수준")
        elif pct > 0:
            lines.append(f"Institutional Ownership: {pct}% — 낮은 기관 관심, 지지 기반 부족 가능성")
        else:
            lines.append(f"Institutional Ownership: {pct}% — 기관 보유 없음 (전 세계 기관이 분석 후 패스한 종목)")
    else:
        lines.append("Institutional Ownership: 데이터 없음")

    # 기관 수 해석
    if count is not None:
        if count == 0:
            lines.append(f"Number of Institutional Holders: {count} — 기관 없음, 강한 경고 신호")
        elif count < 20:
            lines.append(f"Number of Institutional Holders: {count} — O'Neil 최소 기준(20개) 미달")
        elif count < 100:
            lines.append(f"Number of Institutional Holders: {count} — O'Neil 최소 기준 충족 (소형주 적정 수준)")
        elif count < 500:
            lines.append(f"Number of Institutional Holders: {count} — 양호한 기관 보유")
        elif count < 2000:
            lines.append(f"Number of Institutional Holders: {count} — 높은 기관 보유 (과잉보유 경계 모니터링)")
        else:
            lines.append(f"Number of Institutional Holders: {count} — 과잉보유(Overowned) 위험 구간 (AIG는 3,600개+ 후 폭락)")
    else:
        lines.append("Number of Institutional Holders: 데이터 없음")

    # 뮤추얼펀드 데이터
    if mf_count is not None:
        lines.append(f"Mutual Fund Holders: {mf_count}개 (질적 판단 핵심 — 성과 우수 액티브 펀드 여부 확인 필요)")

    # Top 기관 보유자
    holders = data.get('top_holders', [])
    if holders:
        lines.append("Top Institutional Holders:")
        for h in holders:
            shares_str = f" ({h['shares']:,} shares)" if 'shares' in h else ""
            lines.append(f"  - {h['name']}{shares_str}")

    # Top 뮤추얼펀드
    mf_holders = data.get('top_mutual_funds', [])
    if mf_holders:
        lines.append("Top Mutual Fund Holders:")
        for h in mf_holders:
            shares_str = f" ({h['shares']:,} shares)" if 'shares' in h else ""
            lines.append(f"  - {h['name']}{shares_str}")

    # 데이터 전혀 없는 경우
    if pct is None and count is None:
        lines.append("기관 보유 데이터 없음 — 소형주이거나 데이터 미제공 종목일 수 있음")

    lines.append("")
    lines.append("[AI 판단 요청 사항]")
    lines.append("- 기관 보유 수준이 O'Neil 최소 기준(20개+)을 충족하는지 평가")
    lines.append("- 과잉보유(Overowned) 위험 여부 판단 (80%+ 또는 수천 개 기관)")
    lines.append("- 보유 기관명에서 Fidelity Contrafund, T. Rowe Price Growth 등 성과 우수 액티브 펀드 식별")
    lines.append("- Vanguard Index, iShares Core 등 패시브 ETF는 종목 선택 의미 없음으로 제외하여 판단")
    lines.append("- 13F 공시 지연(6주) 감안 — 현재 데이터는 최대 13주 전 매수 시점 기준임을 고려")

    if data.get('data_note'):
        lines.append(f"Note: {data['data_note']}")

    lines.append("")
    lines.append(ONEIL_RULE)

    return "\n".join(lines)
