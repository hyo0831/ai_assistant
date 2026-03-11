from __future__ import annotations

import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

UNIVERSE_CACHE_PATH = Path(__file__).parent.parent.parent / "universe.json"

FALLBACK_SYMBOLS = {
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "COST",
    "NFLX", "AMD", "ADBE", "CSCO", "PEP", "INTC", "QCOM", "TXN", "AMGN", "INTU",
    "AMAT", "BKNG", "ISRG", "CMCSA", "PYPL", "GILD", "ADP", "MDLZ", "SBUX", "ADI",
    "LRCX", "MU", "MELI", "PANW", "KLAC", "SNPS", "CDNS", "CRWD", "ORLY", "ABNB",
    "JPM", "BRK-B", "V", "MA", "UNH", "XOM", "LLY", "WMT", "JNJ", "PG",
}


def _fetch_sp500_symbols() -> set[str]:
    ua = {"User-Agent": "Mozilla/5.0"}
    sp_url = "https://en.wikipedia.org/w/index.php?title=List_of_S%26P_500_companies&action=raw"
    with urllib.request.urlopen(urllib.request.Request(sp_url, headers=ua), timeout=10) as resp:
        sp_raw = resp.read().decode("utf-8", errors="ignore")
    return {
        m.group(1).strip().upper().replace(".", "-")
        for m in re.finditer(r"\|\{\{(?:NyseSymbol|NasdaqSymbol)\|([A-Za-z0-9\.\-]+)", sp_raw)
    }


def _fetch_nasdaq_symbols() -> set[str]:
    ua = {"User-Agent": "Mozilla/5.0"}
    nq_url = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqtraded.txt"
    with urllib.request.urlopen(urllib.request.Request(nq_url, headers=ua), timeout=10) as resp:
        nq_raw = resp.read().decode("utf-8", errors="ignore")

    symbols = set()
    for line in nq_raw.splitlines():
        if "|" not in line or line.startswith("Symbol|") or line.startswith("File Creation Time"):
            continue
        cols = line.split("|")
        if len(cols) < 12:
            continue
        nasdaq_traded = cols[0].strip().upper()
        symbol = cols[1].strip().upper().replace(".", "-")
        listing_exchange = cols[3].strip().upper()
        etf = cols[5].strip().upper()
        test_issue = cols[7].strip().upper()
        nextshares = cols[11].strip().upper()
        if not symbol or symbol == "NAN":
            continue
        if nasdaq_traded != "Y":
            continue
        if listing_exchange != "Q":
            continue
        if test_issue == "Y" or etf == "Y" or nextshares == "Y":
            continue
        if re.search(r"[^A-Z0-9\.-]", symbol):
            continue
        symbols.add(symbol)
    return symbols


def refresh_universe() -> dict:
    """S&P500 + NASDAQ 종목 리스트를 새로 가져와서 universe.json에 저장."""
    print("[universe] S&P500 종목 fetch 중...")
    sp500 = _fetch_sp500_symbols()
    print(f"[universe] S&P500: {len(sp500)}개")

    print("[universe] NASDAQ 종목 fetch 중...")
    nasdaq = _fetch_nasdaq_symbols()
    print(f"[universe] NASDAQ: {len(nasdaq)}개")

    # GOOG(C주)는 GOOGL(A주)로 통합 — 중복 제거
    all_syms_raw = sp500 | nasdaq
    all_syms_raw.discard("GOOG")
    all_symbols = sorted(all_syms_raw)
    sp500.discard("GOOG")
    sp500_list = sorted(sp500)

    data = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "sp500_count": len(sp500),
        "nasdaq_count": len(nasdaq),
        "total_count": len(all_symbols),
        "sp500_symbols": sp500_list,
        "all_symbols": all_symbols,
    }

    UNIVERSE_CACHE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"[universe] 저장 완료: {UNIVERSE_CACHE_PATH} (총 {len(all_symbols)}개)")
    return data


def load_universe() -> dict | None:
    """저장된 universe.json 로드. 없으면 None 반환."""
    if not UNIVERSE_CACHE_PATH.exists():
        return None
    try:
        return json.loads(UNIVERSE_CACHE_PATH.read_text())
    except Exception:
        return None


def get_us_index_universe() -> set[str]:
    """캐시된 유니버스 로드. 없으면 실시간 fetch."""
    cached = load_universe()
    if cached and cached.get("all_symbols"):
        return set(cached["all_symbols"])

    print("[universe] 캐시 없음 — 실시간 fetch 중...")
    try:
        data = refresh_universe()
        return set(data["all_symbols"])
    except Exception as exc:
        print(f"[universe] fetch 실패, fallback 사용: {exc}")
        return FALLBACK_SYMBOLS


def get_sp500_symbols() -> set[str]:
    """캐시된 S&P500 목록 로드. 없으면 실시간 fetch."""
    cached = load_universe()
    if cached and cached.get("sp500_symbols"):
        return set(cached["sp500_symbols"])

    try:
        return _fetch_sp500_symbols()
    except Exception:
        return set()


if __name__ == "__main__":
    data = refresh_universe()
    print(f"\nS&P500: {data['sp500_count']}개")
    print(f"NASDAQ: {data['nasdaq_count']}개")
    print(f"전체:   {data['total_count']}개")
    print(f"저장위치: {UNIVERSE_CACHE_PATH}")
