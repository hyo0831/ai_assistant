#!/usr/bin/env python3
"""
ORION 투자 진단 시스템 v0.4  ─  터미널
주식(국내/해외) · 코인  +  OpenAI GPT-4o
"""

import sys
from datetime import datetime

from modules.survey    import load_survey, run_survey
from modules.processor import process_trades
from modules.ai_report import ai_analyze, ai_personality_analyze


# ══════════════════════════════════════════════════════════════════
#  유틸
# ══════════════════════════════════════════════════════════════════

def bar(title=""):
    print("\n" + "=" * 62)
    if title:
        print(f"  {title}")
        print("=" * 62)


def choose(prompt: str, options: list) -> str:
    print(f"\n  {prompt}")
    for i, opt in enumerate(options, 1):
        print(f"    {i}. {opt}")
    while True:
        sel = input("  선택 → ").strip()
        if sel.isdigit() and 1 <= int(sel) <= len(options):
            return options[int(sel) - 1]
        print(f"  1 ~ {len(options)} 사이 숫자를 입력하세요.")


def stub_exit(name: str):
    print(f"\n  [{name}]는 현재 준비 중입니다. 빠른 시일 내 지원 예정입니다.")
    print("  → 현재는 '기본 투자성향 진단' 모드를 이용하시거나")
    print("    주식은 한국투자증권, 코인은 업비트를 선택해 주세요.")
    sys.exit(0)


# ══════════════════════════════════════════════════════════════════
#  Mode 1 : API 키로 투자 등급 받기
# ══════════════════════════════════════════════════════════════════

def select_grade_exchange() -> tuple[str, str]:
    """(market_type, exchange_id) 반환"""
    bar("시장 선택")
    market = choose("어떤 시장을 분석하시겠습니까?", ["주식", "코인"])

    if market == "주식":
        region = choose("국내 / 해외를 선택하세요:", ["국내", "해외"])
        broker = choose(
            "증권사를 선택하세요:",
            ["한국투자증권", "키움 (준비중)", "미래에셋 (준비중)"],
        )
        if "준비중" in broker:
            stub_exit(broker.replace(" (준비중)", ""))

        market_type = "korean" if region == "국내" else "abroad"
        exchange_id = {
            ("국내", "한국투자증권"): "kis_domestic",
            ("해외", "한국투자증권"): "kis_abroad",
        }[(region, "한국투자증권")]

    else:  # 코인
        exchange = choose(
            "거래소를 선택하세요:",
            ["업비트", "빗썸 (준비중)", "비트겟 (준비중)", "바이낸스 (준비중)"],
        )
        if "준비중" in exchange:
            stub_exit(exchange.replace(" (준비중)", ""))

        market_type = "coin"
        exchange_id = "upbit"

    return market_type, exchange_id


def collect_credentials(exchange_id: str) -> dict:
    bar("API 키 입력")

    if exchange_id in ("kis_domestic", "kis_abroad"):
        return {
            "app_key":    input("  KIS App Key             : ").strip(),
            "app_secret": input("  KIS App Secret          : ").strip(),
            "account_no": input("  계좌번호 (예: 50123456-01) : ").strip(),
            "is_mock":    input("  모의투자 계좌? (y/n)      : ").strip().lower() == "y",
        }

    if exchange_id == "upbit":
        return {
            "access_key": input("  Upbit Access Key  : ").strip(),
            "secret_key": input("  Upbit Secret Key  : ").strip(),
        }

    raise ValueError(f"알 수 없는 거래소: {exchange_id}")


def get_client(exchange_id: str, creds: dict):
    if exchange_id == "kis_domestic":
        from modules.clients.kis import KISDomesticClient
        return KISDomesticClient(**creds)
    if exchange_id == "kis_abroad":
        from modules.clients.kis import KISAbroadClient
        return KISAbroadClient(**creds)
    if exchange_id == "upbit":
        from modules.clients.upbit import UpbitClient
        return UpbitClient(**creds)
    raise ValueError(f"클라이언트 없음: {exchange_id}")


def run_grade_mode():
    """실거래 데이터 수집 → 지표 → 설문 → AI 등급 분석"""

    # 거래소 선택
    market_type, exchange_id = select_grade_exchange()

    # API 키 입력
    creds      = collect_credentials(exchange_id)
    openai_key = input("\n  OpenAI API Key : ").strip()

    # 데이터 수집
    bar("데이터 수집 중")
    client = get_client(exchange_id, creds)
    try:
        client.authenticate()
        raw = client.get_trade_history(days=180)
    except Exception as e:
        print(f"\n  [오류] 데이터 수집 실패: {e}")
        sys.exit(1)

    if not raw:
        print("  체결 내역이 없습니다. 종료합니다.")
        sys.exit(0)

    # 지표 산출
    bar("지표 산출 중")
    metrics  = process_trades(raw, market_type)
    currency = metrics.get("currency", "")

    if metrics.get("total_trades", 0) == 0:
        print(f"  [경고] {metrics.get('error', '완료된 거래 없음')}")
        print("  미청산 포지션만 존재하거나 데이터가 부족합니다.")
        print("  설문과 AI 분석은 데이터 없이 진행합니다.\n")
    else:
        print(f"  완결 거래   : {metrics['total_trades']}건")
        print(f"  승률        : {metrics['win_rate']}%")
        print(f"  손익비      : {metrics['rr_ratio']} : 1")
        print(f"  MDD         : {metrics['mdd']:,.2f} {currency}")

    # 설문
    survey_data = load_survey(market_type)
    answers     = run_survey(survey_data)

    # AI 등급 분석
    bar("AI 융합 분석 중")
    print("  GPT-4o에 분석 요청 중...\n")
    try:
        analysis, score, tier = ai_analyze(metrics, answers, market_type, openai_key)
    except Exception as e:
        print(f"  [오류] OpenAI 호출 실패: {e}")
        sys.exit(1)

    # 결과 출력
    bar("최종 진단 결과")
    print(f"\n  ★ 등급 : [{tier}]  |  점수 : {score} / 100\n")
    print("─" * 62)
    print(analysis)
    print("─" * 62)

    _save_result(market_type, exchange_id, metrics,
                 extra_header=f"등급: {tier} | 점수: {score}/100\n",
                 analysis=analysis)


# ══════════════════════════════════════════════════════════════════
#  Mode 2 : 기본 투자성향 진단하기
# ══════════════════════════════════════════════════════════════════

def select_personality_market() -> str:
    """시장 타입만 선택 (거래소 불필요)"""
    bar("시장 선택")
    choice = choose(
        "어떤 시장의 투자 성향을 진단하시겠습니까?",
        ["국내주식", "해외주식", "코인"],
    )
    return {"국내주식": "korean", "해외주식": "abroad", "코인": "coin"}[choice]


def run_personality_mode():
    """설문만으로 투자 성향 닉네임 분석 (거래 데이터·등급 없음)"""

    market_type = select_personality_market()
    openai_key  = input("\n  OpenAI API Key : ").strip()

    # 설문
    survey_data = load_survey(market_type)
    answers     = run_survey(survey_data)

    # AI 성향 분석
    bar("AI 투자 성향 분석 중")
    print("  GPT-4o에 분석 요청 중...\n")
    try:
        analysis, nickname = ai_personality_analyze(answers, market_type, openai_key)
    except Exception as e:
        print(f"  [오류] OpenAI 호출 실패: {e}")
        sys.exit(1)

    # 결과 출력
    bar("투자 성향 진단 결과")
    if nickname:
        print(f"\n  나의 투자 성향 유형 : [{nickname}]\n")
    print("─" * 62)
    print(analysis)
    print("─" * 62)

    _save_result(market_type, "성향진단", {},
                 extra_header=f"성향 유형: {nickname}\n",
                 analysis=analysis)


# ══════════════════════════════════════════════════════════════════
#  공통 저장
# ══════════════════════════════════════════════════════════════════

def _save_result(market_type, exchange_id, metrics, extra_header, analysis):
    save = input("\n  결과를 result.txt로 저장하시겠습니까? (y/n) : ").strip().lower()
    if save != "y":
        return
    with open("result.txt", "w", encoding="utf-8") as f:
        f.write(f"ORION 투자 진단 결과\n생성: {datetime.now():%Y-%m-%d %H:%M}\n\n")
        f.write(f"시장: {market_type} | 거래소: {exchange_id}\n")
        f.write(extra_header + "\n")
        if metrics:
            f.write("=== 매매 지표 ===\n")
            for k, v in metrics.items():
                f.write(f"{k}: {v}\n")
            f.write("\n")
        f.write("=== AI 분석 ===\n")
        f.write(analysis)
    print("  → result.txt 저장 완료\n")


# ══════════════════════════════════════════════════════════════════
#  Main
# ══════════════════════════════════════════════════════════════════

def main():
    bar("ORION 투자 진단 시스템 v0.4")
    print("  밤하늘의 사냥꾼, 당신의 투자 본능을 분석합니다.")
    print("  주식(국내/해외·한국투자증권)  ·  코인(업비트)  +  OpenAI GPT-4o\n")

    mode = choose(
        "시작 방식을 선택하세요:",
        [
            "API 키로 투자 등급 받기  (거래 데이터 + 설문 → 등급/점수)",
            "기본 투자성향 진단하기   (설문만 → 성향 닉네임, API 키 불필요)",
        ],
    )

    if mode.startswith("API"):
        run_grade_mode()
    else:
        run_personality_mode()


if __name__ == "__main__":
    main()
