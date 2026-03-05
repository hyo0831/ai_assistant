from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed


def _safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def fetch_symbol_snapshot(symbol: str, bench_6m: float, bench_12m: float, include_info: bool = False):
    import yfinance as yf

    t = yf.Ticker(symbol)
    hist = t.history(period="1y", interval="1d", auto_adjust=False)
    if hist is None or hist.empty or len(hist) < 120:
        return None

    close = hist["Close"].dropna()
    high = hist["High"].dropna()
    vol = hist["Volume"].dropna()
    if close.empty or high.empty:
        return None

    price = _safe_float(close.iloc[-1], 0.0)
    high_52w = _safe_float(high.max(), 0.0)
    from_high_pct = round((price / high_52w) * 100.0, 1) if high_52w > 0 else 0.0

    vol20 = _safe_float(vol.tail(20).mean(), 0.0) if not vol.empty else 0.0
    last_vol = _safe_float(vol.iloc[-1], 0.0) if not vol.empty else 0.0
    vol_ratio = round(last_vol / vol20, 2) if vol20 > 0 else 1.0

    n = len(close)
    i6 = max(0, n - 126)
    i12 = 0
    c6 = _safe_float(close.iloc[i6], 0.0)
    c12 = _safe_float(close.iloc[i12], 0.0)
    ret_6m = ((price / c6) - 1.0) if c6 > 0 else 0.0
    ret_12m = ((price / c12) - 1.0) if c12 > 0 else 0.0
    rs_raw = (ret_6m - bench_6m) * 0.6 + (ret_12m - bench_12m) * 0.4

    info = {}
    fast_info = {}
    try:
        fast_info = t.fast_info or {}
    except Exception:
        fast_info = {}
    if include_info:
        for i in range(4):
            try:
                info = t.info or {}
                if info:
                    break
            except Exception:
                pass
            time.sleep(0.35 * (i + 1))

    market_cap = _safe_float(
        fast_info.get("market_cap")
        or info.get("marketCap")
        or info.get("market_cap"),
        0.0,
    )
    eps_growth = _safe_float(
        info.get("earningsQuarterlyGrowth")
        if info.get("earningsQuarterlyGrowth") is not None else info.get("earningsGrowth"),
        0.0,
    ) * 100.0
    revenue_growth = _safe_float(info.get("revenueGrowth"), 0.0) * 100.0

    return {
        "symbol": symbol,
        "name": info.get("shortName") or info.get("longName") or symbol,
        "sector": info.get("sector") or "N/A",
        "industry": info.get("industry") or "N/A",
        "price": round(price, 2),
        "from_high_pct": round(from_high_pct, 1),
        "eps_growth": round(eps_growth, 1),
        "revenue_growth": round(revenue_growth, 1),
        "vol_ratio": round(vol_ratio, 2),
        "market_cap": int(market_cap) if market_cap > 0 else 0,
        "rs_raw": round(rs_raw, 4),
    }


def collect_snapshots_throttled(
    symbols: list[str],
    bench_6m: float,
    bench_12m: float,
    include_info: bool,
    workers: int,
    batch_size: int,
    pause_sec: float,
) -> dict[str, dict]:
    workers = max(1, workers)
    batch_size = max(1, batch_size)
    out = {}
    for i in range(0, len(symbols), batch_size):
        chunk = symbols[i:i + batch_size]
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {
                ex.submit(fetch_symbol_snapshot, sym, bench_6m, bench_12m, include_info): sym
                for sym in chunk
            }
            for f in as_completed(futures):
                sym = futures[f]
                try:
                    row = f.result()
                    if row:
                        out[sym] = row
                except Exception:
                    continue
        if pause_sec > 0:
            time.sleep(pause_sec)
    return out
