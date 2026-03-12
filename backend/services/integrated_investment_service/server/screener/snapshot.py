from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterator


def _chunked(lst: list, size: int) -> Iterator[list]:
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


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


def _extract_snapshot_from_batch(
    df,
    symbol: str,
    bench_6m: float,
    bench_12m: float,
) -> dict | None:
    """MultiIndex batch DataFrame에서 단일 심볼 스냅샷 추출."""
    import pandas as pd

    try:
        # df가 단일 심볼인 경우(chunk size=1)는 MultiIndex가 아닐 수 있음
        if isinstance(df.columns, pd.MultiIndex):
            if symbol not in df.columns.get_level_values(0):
                return None
            sym_df = df.xs(symbol, axis=1, level=0)
        else:
            sym_df = df

        sym_df = sym_df.dropna(how="all")
        if sym_df is None or len(sym_df) < 120:
            return None

        close = sym_df["Close"].dropna()
        high = sym_df["High"].dropna()
        vol = sym_df["Volume"].dropna()
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
        c6 = _safe_float(close.iloc[i6], 0.0)
        c12 = _safe_float(close.iloc[0], 0.0)
        ret_6m = ((price / c6) - 1.0) if c6 > 0 else 0.0
        ret_12m = ((price / c12) - 1.0) if c12 > 0 else 0.0
        rs_raw = (ret_6m - bench_6m) * 0.6 + (ret_12m - bench_12m) * 0.4

        return {
            "symbol": symbol,
            "name": symbol,
            "sector": "N/A",
            "industry": "N/A",
            "price": round(price, 2),
            "from_high_pct": round(from_high_pct, 1),
            "eps_growth": 0.0,
            "revenue_growth": 0.0,
            "vol_ratio": round(vol_ratio, 2),
            "market_cap": 0,
            "rs_raw": round(rs_raw, 4),
        }
    except Exception:
        return None


def collect_snapshots_batch(
    symbols: list[str],
    bench_6m: float,
    bench_12m: float,
    batch_size: int = 200,
    pause_sec: float = 10.0,
) -> dict[str, dict]:
    """yf.download() 배치 방식으로 가격 데이터 수집 (rate limit 최소화).

    4000개 종목 기준 ~20배치 × 10초 sleep → 약 15분 소요.
    펀더멘털(EPS, 매출, 시총, 이름, 섹터)은 Phase 2에서 fetch_symbol_snapshot()으로 처리.
    """
    import yfinance as yf

    out: dict[str, dict] = {}
    chunks = list(_chunked(symbols, batch_size))
    for idx, chunk in enumerate(chunks):
        print(f"[snapshot] 배치 {idx + 1}/{len(chunks)} — {len(chunk)}개 다운로드 중...")
        try:
            df = yf.download(
                chunk,
                period="1y",
                group_by="ticker",
                auto_adjust=False,
                progress=False,
                threads=True,
            )
            for sym in chunk:
                row = _extract_snapshot_from_batch(df, sym, bench_6m, bench_12m)
                if row:
                    out[sym] = row
        except Exception as exc:
            print(f"[snapshot] 배치 {idx + 1} 실패: {exc}")

        if pause_sec > 0 and idx < len(chunks) - 1:
            time.sleep(pause_sec)

    print(f"[snapshot] 배치 수집 완료: {len(out)}/{len(symbols)}개")
    return out


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
