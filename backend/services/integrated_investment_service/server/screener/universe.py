from __future__ import annotations

import re


def get_us_index_universe() -> set[str]:
    """S&P500 + NASDAQ 전체 유니버스 구성."""
    fallback = {
        "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "GOOG", "META", "TSLA", "AVGO", "COST",
        "NFLX", "AMD", "ADBE", "CSCO", "PEP", "INTC", "QCOM", "TXN", "AMGN", "INTU",
        "AMAT", "BKNG", "ISRG", "CMCSA", "PYPL", "GILD", "ADP", "MDLZ", "SBUX", "ADI",
        "LRCX", "MU", "MELI", "PANW", "KLAC", "SNPS", "CDNS", "CRWD", "ORLY", "ABNB",
        "JPM", "BRK-B", "V", "MA", "UNH", "XOM", "LLY", "WMT", "JNJ", "PG",
    }
    try:
        import urllib.request

        ua = {"User-Agent": "Mozilla/5.0"}
        sp_url = "https://en.wikipedia.org/w/index.php?title=List_of_S%26P_500_companies&action=raw"
        nq_all_url = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqtraded.txt"

        with urllib.request.urlopen(urllib.request.Request(sp_url, headers=ua), timeout=10) as resp:
            sp_raw = resp.read().decode("utf-8", errors="ignore")
        with urllib.request.urlopen(urllib.request.Request(nq_all_url, headers=ua), timeout=10) as resp:
            nq_all_raw = resp.read().decode("utf-8", errors="ignore")

        sp500_symbols = {
            m.group(1).strip().upper().replace(".", "-")
            for m in re.finditer(r"\|\{\{(?:NyseSymbol|NasdaqSymbol)\|([A-Za-z0-9\.\-]+)", sp_raw)
        }

        ndq_symbols = set()
        for line in nq_all_raw.splitlines():
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
            ndq_symbols.add(symbol)

        symbols = {s for s in (sp500_symbols | ndq_symbols) if s and s != "NAN"}
        if len(symbols) < 700:
            print(f"[WARN] universe parse size too small ({len(symbols)}), fallback 사용")
            return fallback
        return symbols
    except Exception as exc:
        print(f"[WARN] index universe fetch failed, fallback 사용: {exc}")
        return fallback


def get_sp500_symbols() -> set[str]:
    try:
        import urllib.request

        ua = {"User-Agent": "Mozilla/5.0"}
        sp_url = "https://en.wikipedia.org/w/index.php?title=List_of_S%26P_500_companies&action=raw"
        with urllib.request.urlopen(urllib.request.Request(sp_url, headers=ua), timeout=10) as resp:
            sp_raw = resp.read().decode("utf-8", errors="ignore")
        symbols = {
            m.group(1).strip().upper().replace(".", "-")
            for m in re.finditer(r"\|\{\{(?:NyseSymbol|NasdaqSymbol)\|([A-Za-z0-9\.\-]+)", sp_raw)
        }
        return symbols
    except Exception:
        return set()
