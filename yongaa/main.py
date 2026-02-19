#!/usr/bin/env python3
"""
ORION 투자 진단 시스템 v0.3  ─  터미널 멀티 시장
주식(국내/해외) · 코인  ×  6개 거래소  +  OpenAI GPT-4o
"""

import sys
from datetime import datetime

from modules.survey    import load_survey, run_survey
from modules.processor import process_trades
from modules.ai_report import ai_analyze


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


# ══════════════════════════════════════════════════════════════════
#  Step 1 : 시장 & 거래소 선택
# ══════════════════════════════════════════════════════════════════

def select_flow() -> tuple[str, str]:
    """(market_type, exchange_id) 반환"""
    bar("Step 1. 시장 선택")
    market = choose("어떤 시장을 분석하시겠습니까?", ["주식", "코인"])

    if market == "주식":
        region = choose("국내 / 해외를 선택하세요:", ["국내", "해외"])
        broker = choose("증권사를 선택하세요:", ["키움", "한국투자증권", "미래에셋"])
        market_type = "korean" if region == "국내" else "abroad"
        exchange_id = {
            ("국내", "키움"):        "kiwoom",
            ("국내", "한국투자증권"): "kis_domestic",
            ("국내", "미래에셋"):    "mirae_domestic",
            ("해외", "키움"):        "kiwoom_abroad",
            ("해외", "한국투자증권"): "kis_abroad",
            ("해외", "미래에셋"):    "mirae_abroad",
        }[(region, broker)]

    else:  # 코인
        exchange = choose("거래소를 선택하세요:", ["업비트", "빗썸", "비트겟", "바이낸스"])
        market_type = "coin"
        exchange_id = {
            "업비트": "upbit",
            "빗썸":   "bithumb",
            "비트겟": "bitget",
            "바이낸스": "binance",
        }[exchange]

    return market_type, exchange_id


# ══════════════════════════════════════════════════════════════════
#  Step 2 : 거래소별 API 키 수집
# ══════════════════════════════════════════════════════════════════

def collect_credentials(exchange_id: str) -> dict:
    """거래소별 API 자격증명 수집"""
    bar("Step 2. API 키 입력")

    # ── 한국투자증권 ──────────────────────────────────────────────
    if exchange_id in ("kis_domestic", "kis_abroad"):
        return {
            "app_key":    input("  KIS App Key             : ").strip(),
            "app_secret": input("  KIS App Secret          : ").strip(),
            "account_no": input("  계좌번호 (예: 50123456-01) : ").strip(),
            "is_mock":    input("  모의투자 계좌? (y/n)      : ").strip().lower() == "y",
        }

    # ── 미래에셋 ─────────────────────────────────────────────────
    if exchange_id in ("mirae_domestic", "mirae_abroad"):
        return {
            "app_key":    input("  미래에셋 App Key        : ").strip(),
            "app_secret": input("  미래에셋 App Secret     : ").strip(),
            "account_no": input("  계좌번호 (예: 12345678-01) : ").strip(),
            "is_mock":    input("  모의투자 계좌? (y/n)      : ").strip().lower() == "y",
        }

    # ── 키움 (GUI 로그인 → API Key 불필요) ───────────────────────
    if exchange_id in ("kiwoom", "kiwoom_abroad"):
        print("\n  [키움] 키움 HTS(영웅문)가 실행 중이어야 합니다.")
        print("  API Key 없이 GUI 팝업 로그인 방식으로 진행됩니다.")
        input("  준비 완료 시 Enter를 누르세요...")
        return {}   # 자격증명 불필요 (CommConnect 사용)

    # ── 업비트 ───────────────────────────────────────────────────
    if exchange_id == "upbit":
        return {
            "access_key": input("  Upbit Access Key  : ").strip(),
            "secret_key": input("  Upbit Secret Key  : ").strip(),
        }

    # ── 빗썸 ─────────────────────────────────────────────────────
    if exchange_id == "bithumb":
        raw_coins = input(
            "  Bithumb Con Key    : "
        ).strip()
        api_key    = raw_coins
        api_secret = input("  Bithumb Secret Key : ").strip()
        coins_inp  = input(
            "  조회 코인 (Enter=기본값 BTC ETH XRP SOL 등) : "
        ).strip()
        coins = coins_inp.upper().split() if coins_inp else None
        return {"api_key": api_key, "api_secret": api_secret, "coins": coins}

    # ── 비트겟 ───────────────────────────────────────────────────
    if exchange_id == "bitget":
        return {
            "api_key":    input("  Bitget API Key    : ").strip(),
            "api_secret": input("  Bitget Secret Key : ").strip(),
            "passphrase": input("  Bitget Passphrase : ").strip(),
        }

    # ── 바이낸스 ─────────────────────────────────────────────────
    if exchange_id == "binance":
        return {
            "api_key":    input("  Binance API Key    : ").strip(),
            "api_secret": input("  Binance API Secret : ").strip(),
            "symbols":    input(
                "  조회할 심볼 (스페이스로 구분, 예: BTCUSDT ETHUSDT) : "
            ).strip().split(),
        }

    raise ValueError(f"알 수 없는 거래소: {exchange_id}")


# ══════════════════════════════════════════════════════════════════
#  클라이언트 팩토리
# ══════════════════════════════════════════════════════════════════

def get_client(exchange_id: str, creds: dict):
    if exchange_id == "kis_domestic":
        from modules.clients.kis import KISDomesticClient
        return KISDomesticClient(**creds)

    if exchange_id == "kis_abroad":
        from modules.clients.kis import KISAbroadClient
        return KISAbroadClient(**creds)

    if exchange_id == "kiwoom":
        from modules.clients.kiwoom import KiwoomDomesticClient
        return KiwoomDomesticClient()

    if exchange_id == "kiwoom_abroad":
        from modules.clients.kiwoom import KiwoomAbroadClient
        return KiwoomAbroadClient()

    if exchange_id == "mirae_domestic":
        from modules.clients.mirae import MiraeDomesticClient
        return MiraeDomesticClient(**creds)

    if exchange_id == "mirae_abroad":
        from modules.clients.mirae import MiraeAbroadClient
        return MiraeAbroadClient(**creds)

    if exchange_id == "upbit":
        from modules.clients.upbit import UpbitClient
        return UpbitClient(**creds)

    if exchange_id == "bithumb":
        from modules.clients.bithumb import BithumbClient
        return BithumbClient(**creds)

    if exchange_id == "bitget":
        from modules.clients.bitget import BitgetClient
        return BitgetClient(**creds)

    if exchange_id == "binance":
        from modules.clients.binance_client import BinanceClient
        return BinanceClient(**creds)

    raise ValueError(f"클라이언트 없음: {exchange_id}")


# ══════════════════════════════════════════════════════════════════
#  Main
# ══════════════════════════════════════════════════════════════════

def main():
    bar("ORION 투자 진단 시스템 v0.3")
    print("  주식(국내/해외) · 코인  ×  한투·키움·미래에셋·업비트·빗썸·비트겟·바이낸스")
    print("  + OpenAI GPT-4o 융합 분석\n")

    # Step 1: 시장 & 거래소 선택
    market_type, exchange_id = select_flow()

    # Step 2: API 키 입력
    creds      = collect_credentials(exchange_id)
    openai_key = input("\n  OpenAI API Key : ").strip()

    # Step 3: 데이터 수집
    bar("Step 3. 데이터 수집")
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

    # Step 4: 지표 산출
    bar("Step 4. 지표 산출")
    metrics = process_trades(raw, market_type)
    currency = metrics.get("currency", "")

    if metrics.get("total_trades", 0) == 0:
        print(f"  [경고] {metrics.get('error', '완료된 거래 없음')}")
        print("  → 미청산 포지션만 존재하거나 데이터가 부족합니다.")
        print("  → 설문과 AI 분석은 데이터 없이 진행합니다.\n")
    else:
        print(f"  완결 거래   : {metrics['total_trades']}건")
        print(f"  승률        : {metrics['win_rate']}%")
        print(f"  손익비      : {metrics['rr_ratio']} : 1")
        print(f"  MDD         : {metrics['mdd']:,.2f} {currency}")

    # Step 5: 설문
    survey_data = load_survey(market_type)
    answers     = run_survey(survey_data)

    # Step 6: AI 분석
    bar("Step 6. AI 융합 분석")
    print("  GPT-4o에 분석 요청 중...\n")
    try:
        analysis, score, tier = ai_analyze(metrics, answers, market_type, openai_key)
    except Exception as e:
        print(f"  [오류] OpenAI 호출 실패: {e}")
        sys.exit(1)

    # Step 7: 결과 출력
    bar("최종 진단 결과")
    print(f"\n  ★ 등급 : [{tier}]  |  점수 : {score} / 100\n")
    print("─" * 62)
    print(analysis)
    print("─" * 62)

    # 저장 옵션
    save = input("\n  결과를 result.txt로 저장하시겠습니까? (y/n) : ").strip().lower()
    if save == "y":
        with open("result.txt", "w", encoding="utf-8") as f:
            f.write(f"ORION 투자 진단 결과\n생성: {datetime.now():%Y-%m-%d %H:%M}\n\n")
            f.write(f"시장: {market_type} | 거래소: {exchange_id}\n")
            f.write(f"등급: {tier} | 점수: {score}/100\n\n")
            f.write("=== 매매 지표 ===\n")
            for k, v in metrics.items():
                f.write(f"{k}: {v}\n")
            f.write("\n=== AI 분석 ===\n")
            f.write(analysis)
        print("  → result.txt 저장 완료\n")


if __name__ == "__main__":
    main()
