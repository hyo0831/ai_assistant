"""
AI 융합 분석 모듈
- ai_analyze()           : 실거래 데이터 + 설문 → 등급/점수 리포트
- ai_personality_analyze(): 설문만 → 투자 성향 닉네임 리포트
"""

from openai import OpenAI

# ══════════════════════════════════════════════════════════════════
#  1. 등급 모드 (실거래 데이터 + 설문)
# ══════════════════════════════════════════════════════════════════

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
    score += min(40, m.get("win_rate",         0) * 0.4)
    score += min(40, m.get("rr_ratio",         0) * 13.3)
    score -= min(20, m.get("martingale_count", 0) * 2)
    return max(0, min(100, int(score)))


def get_tier(score: int) -> str:
    for threshold, tier in TIERS:
        if score >= threshold:
            return tier
    return "브론즈"


_BASE_GRADE = """
당신은 ORION 투자 진단 AI입니다.
사용자의 실제 매매 데이터와 설문 응답을 교차 분석하여 아래 항목을 순서대로 출력하세요.
마크다운 없이 깔끔한 텍스트로만 작성합니다.

[1] 매매 스타일 요약 (3줄 이내)
[2] 강점 2가지 / 약점 2가지
[3] 설문 vs 실제 데이터 일치 여부 (원칙 준수율 판단)
[4] 최적 TP/SL 수치 추천 (과거 데이터 기반 근거 포함)
[5] AI 한마디 (핵심 조언 1문장)
"""

GRADE_PROMPTS = {
    "korean": _BASE_GRADE + """
추가 지침 (국내 주식):
- 상하한가·VI 제도, 테마주 쏠림 현상을 반드시 분석에 반영하세요.
- 등급 산정 시 수익률(총손익)을 가장 높은 가중치로 사용하세요.
""",
    "abroad": _BASE_GRADE + """
추가 지침 (해외 주식):
- FOMC·CPI 등 매크로 이벤트 대응 능력을 핵심 지표로 분석하세요.
- 상하한가 없는 변동성 환경과 환율 리스크를 반드시 언급하세요.
""",
    "coin": _BASE_GRADE + """
추가 지침 (코인):
- 24시간 시장 특성, 레버리지 리스크, 청산 위험을 반드시 언급하세요.
- BTC 도미넌스 인식 수준과 공포탐욕지수 활용 여부를 평가하세요.
- 단타/스윙/홀딩 비중을 분석하여 코인 트레이더 유형을 분류하세요.
""",
}


def _build_grade_message(metrics: dict, survey: dict, score: int, tier: str) -> str:
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

    lines += ["", "[설문 응답]"]
    for i in range(1, 11):
        val = survey.get(f"q{i}", "")
        if val:
            lines.append(f"  Q{i}: {val}")

    return "\n".join(lines)


def ai_analyze(metrics: dict, survey: dict, market_type: str, openai_key: str):
    score  = calc_score(metrics)
    tier   = get_tier(score)
    system = GRADE_PROMPTS.get(market_type, GRADE_PROMPTS["korean"])
    user   = _build_grade_message(metrics, survey, score, tier)

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


# ══════════════════════════════════════════════════════════════════
#  2. 투자 성향 닉네임 테이블
# ══════════════════════════════════════════════════════════════════
#
#  ORION 브랜딩 콘셉트:
#    별자리(Constellation) + 동물(Animal) + 투자 스타일
#    "오리온은 밤하늘의 사냥꾼 — 투자자도 각자의 사냥법이 있다"
#
# ── 국내주식 ──────────────────────────────────────────────────────
#  [화살·매]  오리온의 별자리 중 가장 빛나는 '리겔(Rigel)' 에서 영감
#             매(隼): 전고점을 보는 순간 날아드는 돌파형
#  [곰]       큰곰자리(Ursa Major): 느리지만 묵직한 스윙형
#  [여우]     카시오페이아: W자 형태처럼 유연하게 방향을 바꾸는 역발상형
#
# ── 해외주식 ──────────────────────────────────────────────────────
#  [독수리]   독수리자리(Aquila): 나스닥 상공을 선회하는 모멘텀형
#  [올빼미]   처녀자리(Virgo): 밤새 관찰하고 분석하는 가치투자형
#  [고래]     남십자성(Crux): 남반구의 거대한 물살을 타는 매크로형
#
# ── 코인 ─────────────────────────────────────────────────────────
#  [치타]     전갈자리(Scorpius): 독침처럼 빠른 레버리지 단타형
#  [황소]     황소자리(Taurus): BULL 마켓을 믿고 버티는 현물 홀딩형
#  [카멜레온] 쌍둥이자리(Gemini): 두 개의 얼굴처럼 시장에 따라 전략을 바꾸는 스윙형

PERSONALITY_TYPES = {
    "korean": [
        {
            "id":     "rigel_hawk",
            "name":   "리겔의 매 (Rigel Hawk)",
            "symbol": "오리온자리 · 매(隼)",
            "style":  "돌파 단타형",
            "desc":   "전고점이 뚫리는 순간, 누구보다 빠르게 날아드는 사냥꾼. "
                      "거래량 폭발과 돌파 신호에 본능적으로 반응하며 빠른 의사결정이 강점입니다.",
            "traits": ["돌파 매매", "단타/스캘핑", "거래량 중시", "빠른 진출입"],
        },
        {
            "id":     "ursa_bear",
            "name":   "큰곰자리의 곰 (Ursa Bear)",
            "symbol": "큰곰자리 · 곰(熊)",
            "style":  "스윙 안정형",
            "desc":   "천천히 움직이지만 한 번 잡은 먹이는 놓지 않는 수호자. "
                      "눌림목과 지지선에서 묵직하게 진입하고, 추세가 끝날 때까지 보유합니다.",
            "traits": ["눌림목 매수", "스윙 트레이딩", "리스크 관리 중시", "이평선 추종"],
        },
        {
            "id":     "cassiopeia_fox",
            "name":   "카시오페이아 여우 (Cassiopeia Fox)",
            "symbol": "카시오페이아자리 · 여우(狐)",
            "style":  "역발상 전략형",
            "desc":   "모두가 팔 때 사고, 모두가 살 때 파는 역행자. "
                      "테마의 시작을 남보다 먼저 포착하고, 시장 심리를 역이용하는 전략가입니다.",
            "traits": ["역추세 매매", "테마 선점", "낙폭 과대 사냥", "심리 역이용"],
        },
    ],
    "abroad": [
        {
            "id":     "aquila_eagle",
            "name":   "아퀼라의 독수리 (Aquila Eagle)",
            "symbol": "독수리자리 · 독수리(Eagle)",
            "style":  "모멘텀 기술주형",
            "desc":   "나스닥 상공을 선회하며 모멘텀 종목을 사냥하는 공격형 투자자. "
                      "실적 서프라이즈와 추세 돌파 시 과감히 진입하며, 빅테크와 성장주를 선호합니다.",
            "traits": ["모멘텀 투자", "기술주/빅테크", "Earnings Play", "추세 추종"],
        },
        {
            "id":     "virgo_owl",
            "name":   "처녀자리 올빼미 (Virgo Owl)",
            "symbol": "처녀자리 · 올빼미(Owl)",
            "style":  "펀더멘털 분석형",
            "desc":   "밤새 재무제표와 매크로 지표를 분석하는 관찰자. "
                      "월가 애널리스트 리포트와 가이던스를 꼼꼼히 검토하며, 저평가 가치주를 선호합니다.",
            "traits": ["가치투자", "펀더멘털 분석", "FOMC/CPI 대응", "장기 보유"],
        },
        {
            "id":     "crux_whale",
            "name":   "남십자성 고래 (Crux Whale)",
            "symbol": "남십자성 · 고래(Whale)",
            "style":  "매크로 ETF형",
            "desc":   "거대한 물살(매크로 흐름)을 먼저 읽고 올라타는 거시적 투자자. "
                      "레버리지 ETF와 지수 방향성 베팅을 즐기며, 큰 그림을 보고 포지션을 구성합니다.",
            "traits": ["레버리지 ETF", "지수 방향성", "매크로 분석", "분할 익절"],
        },
    ],
    "coin": [
        {
            "id":     "scorpius_cheetah",
            "name":   "전갈자리 치타 (Scorpius Cheetah)",
            "symbol": "전갈자리 · 치타(Cheetah)",
            "style":  "레버리지 단타형",
            "desc":   "독침처럼 빠르고 치명적인 속도로 시장을 공략하는 사냥꾼. "
                      "선물 레버리지와 초단타를 즐기며, 변동성 구간에서 짧고 굵게 수익을 냅니다.",
            "traits": ["레버리지 선물", "초단타/스캘핑", "변동성 활용", "빠른 손절"],
        },
        {
            "id":     "taurus_bull",
            "name":   "황소자리 황소 (Taurus Bull)",
            "symbol": "황소자리 · 황소(Bull)",
            "style":  "현물 홀딩형",
            "desc":   "BTC·ETH를 믿고 반감기와 사이클을 기다리는 장기 보유자. "
                      "온체인 데이터와 시장 사이클을 분석하며, 공포 구간을 매집 기회로 삼습니다.",
            "traits": ["현물 매수", "장기 HODL", "반감기 사이클", "온체인 분석"],
        },
        {
            "id":     "gemini_chameleon",
            "name":   "쌍둥이자리 카멜레온 (Gemini Chameleon)",
            "symbol": "쌍둥이자리 · 카멜레온(Chameleon)",
            "style":  "스윙 적응형",
            "desc":   "두 개의 얼굴처럼 상승장·하락장 모두에서 전략을 바꾸는 멀티 플레이어. "
                      "BTC 도미넌스와 알트 시즌을 읽으며 상황에 맞게 포트폴리오를 재편합니다.",
            "traits": ["스윙 트레이딩", "BTC 도미넌스 활용", "알트 시즌 대응", "멀티 전략"],
        },
    ],
}


# ── 성향 모드 시스템 프롬프트 ─────────────────────────────────────

def _build_personality_system(market_type: str) -> str:
    types = PERSONALITY_TYPES.get(market_type, [])
    type_list = "\n".join(
        f'  {i+1}. [{t["name"]}] — {t["style"]}: {t["desc"]}'
        for i, t in enumerate(types)
    )
    market_label = {"korean": "국내주식", "abroad": "해외주식", "coin": "코인"}.get(market_type, "")

    return f"""당신은 ORION 투자 성향 진단 AI입니다.
사용자의 설문 응답만을 분석하여 아래 3가지 투자자 유형 중 가장 잘 맞는 유형을 선택하고 분석합니다.
점수나 등급은 부여하지 않습니다. 마크다운 없이 깔끔한 텍스트로만 작성합니다.

[{market_label}] 투자자 유형 3가지:
{type_list}

출력 형식 (반드시 이 순서로):
[성향 진단] 유형명 전체 (예: 리겔의 매 (Rigel Hawk))
[한 줄 요약] 이 투자자를 한 문장으로 표현
[성향 분석] 설문 응답을 근거로 왜 이 유형인지 3~4줄 설명
[강점] 이 성향의 타고난 강점 2가지
[주의점] 이 성향이 빠지기 쉬운 함정 2가지
[ORION의 조언] 이 성향에 맞는 핵심 전략 1문장
"""


def _build_personality_message(survey: dict, market_type: str) -> str:
    market_label = {"korean": "국내주식", "abroad": "해외주식", "coin": "코인"}.get(market_type, "")
    lines = [f"[{market_label} 설문 응답]"]
    for i in range(1, 11):
        val = survey.get(f"q{i}", "")
        if val:
            lines.append(f"  Q{i}: {val}")
    return "\n".join(lines)


def ai_personality_analyze(survey: dict, market_type: str, openai_key: str):
    """설문만으로 투자 성향 닉네임 및 분석 반환 → (analysis_text, nickname)"""
    system = _build_personality_system(market_type)
    user   = _build_personality_message(survey, market_type)

    client   = OpenAI(api_key=openai_key)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        temperature=0.75,
    )
    text = response.choices[0].message.content

    # 닉네임 추출 (첫 줄 [성향 진단] 뒤)
    nickname = ""
    for line in text.splitlines():
        if "[성향 진단]" in line:
            nickname = line.replace("[성향 진단]", "").strip()
            break

    return text, nickname
