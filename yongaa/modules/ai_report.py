"""
AI 융합 분석 모듈
- 시장별 시스템 프롬프트 선택
- metrics + survey answers → OpenAI GPT-4o → 분석 리포트
"""

from openai import OpenAI

# ── 티어 테이블 ────────────────────────────────────────────────────
TIERS = [
    (90, "챌린저"),
    (80, "그랜드마스터"),
    (70, "마스터"),
    (60, "다이아몬드"),
    (50, "플래티넘"),
    (40, "골드"),
    (30, "실버"),
    (0,  "브론즈"),
]


def calc_score(m: dict) -> int:
    score  = 0
    score += min(40, m.get("win_rate",         0) * 0.4)   # 승률  최대 40점
    score += min(40, m.get("rr_ratio",         0) * 13.3)  # 손익비 최대 40점
    score -= min(20, m.get("martingale_count", 0) * 2)     # 물타기 페널티
    return max(0, min(100, int(score)))


def get_tier(score: int) -> str:
    for threshold, tier in TIERS:
        if score >= threshold:
            return tier
    return "브론즈"


# ── 시장별 시스템 프롬프트 ─────────────────────────────────────────
_BASE_INSTRUCTIONS = """
당신은 ORION 투자 진단 AI입니다.
사용자의 실제 매매 데이터와 설문 응답을 교차 분석하여 아래 항목을 순서대로 출력하세요.
마크다운 없이 깔끔한 텍스트로만 작성합니다.

[1] 매매 스타일 요약 (3줄 이내)
[2] 강점 2가지 / 약점 2가지
[3] 설문 vs 실제 데이터 일치 여부 (원칙 준수율 판단)
[4] 최적 TP/SL 수치 추천 (과거 데이터 기반 근거 포함)
[5] AI 한마디 (핵심 조언 1문장)
"""

SYSTEM_PROMPTS = {
    "korean": _BASE_INSTRUCTIONS + """
추가 지침 (국내 주식):
- 상하한가·VI 제도, 테마주 쏠림 현상을 반드시 분석에 반영하세요.
- 등급 산정 시 수익률(총손익)을 가장 높은 가중치로 사용하세요.
""",
    "abroad": _BASE_INSTRUCTIONS + """
추가 지침 (해외 주식):
- FOMC·CPI 등 매크로 이벤트 대응 능력을 핵심 지표로 분석하세요.
- 상하한가 없는 변동성 환경과 환율 리스크를 반드시 언급하세요.
- 유저를 '나스닥 서퍼' 또는 '월가 가치 투자자' 유형으로 분류하세요.
""",
    "coin": _BASE_INSTRUCTIONS + """
추가 지침 (코인):
- 24시간 시장 특성, 레버리지 리스크, 청산(liquidation) 위험을 반드시 언급하세요.
- BTC 도미넌스 인식 수준과 공포탐욕지수 활용 여부를 평가하세요.
- 단타/스윙/홀딩 비중을 분석하여 코인 트레이더 유형을 분류하세요.
""",
}


def _build_user_message(metrics: dict, survey: dict, score: int, tier: str) -> str:
    currency = metrics.get("currency", "KRW")
    market   = metrics.get("market_type", "")

    lines = [
        "[실제 매매 데이터 - 최근 180일]",
        f"- 총 완결 거래  : {metrics.get('total_trades', 'N/A')}건",
        f"- 승률          : {metrics.get('win_rate', 'N/A')}%",
        f"- 평균 익절     : +{metrics.get('avg_profit_pct', 'N/A')}%",
        f"- 평균 손절     : -{metrics.get('avg_loss_pct', 'N/A')}%",
        f"- 실질 손익비   : {metrics.get('rr_ratio', 'N/A')} : 1",
        f"- 총 손익       : {metrics.get('total_pnl', 'N/A')} {currency}",
        f"- MDD           : {metrics.get('mdd', 'N/A')} {currency}",
        f"- 평균 보유시간 : {metrics.get('avg_holding_hours', 'N/A')}시간",
        f"- 물타기 횟수   : {metrics.get('martingale_count', 'N/A')}회",
        f"- 종합 점수     : {score}점  →  {tier} 등급",
    ]

    # 시장별 추가 지표
    if market == "coin":
        if "scalp_ratio_pct" in metrics:
            lines.append(f"- 단타 비중(1h↓)  : {metrics['scalp_ratio_pct']}%")
        if "swing_ratio_pct" in metrics:
            lines.append(f"- 스윙 비중(24h↑) : {metrics['swing_ratio_pct']}%")
    elif market == "abroad":
        if "unique_tickers" in metrics:
            lines.append(f"- 거래 종목 수     : {metrics['unique_tickers']}개")
    elif market == "korean":
        if "most_traded_ticker" in metrics:
            lines.append(
                f"- 최다 매매 종목   : {metrics['most_traded_ticker']} "
                f"({metrics.get('most_traded_count', '')}건)"
            )

    lines += [
        "",
        "[설문 응답]",
    ]
    for i in range(1, 11):
        key = f"q{i}"
        val = survey.get(key, "")
        if val:
            lines.append(f"  Q{i}: {val}")

    return "\n".join(lines)


def ai_analyze(metrics: dict, survey: dict, market_type: str, openai_key: str):
    score  = calc_score(metrics)
    tier   = get_tier(score)
    system = SYSTEM_PROMPTS.get(market_type, SYSTEM_PROMPTS["korean"])
    user   = _build_user_message(metrics, survey, score, tier)

    client   = OpenAI(api_key=openai_key)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        temperature=0.7,
    )
    return response.choices[0].message.content, score, tier
