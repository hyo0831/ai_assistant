from __future__ import annotations

import json
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable


def _safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def fetch_yahoo_growth_snapshot(symbol: str) -> dict:
    try:
        sym = urllib.parse.quote(symbol)
        url = (
            f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{sym}"
            "?modules=financialData,price"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode())
        result = (((data or {}).get("quoteSummary") or {}).get("result") or [{}])[0]
        fin = result.get("financialData") or {}
        price = result.get("price") or {}

        def _raw(v):
            if isinstance(v, dict):
                return v.get("raw")
            return v

        return {
            "eps_growth": _safe_float(_raw(fin.get("earningsGrowth")), 0.0) * 100.0,
            "revenue_growth": _safe_float(_raw(fin.get("revenueGrowth")), 0.0) * 100.0,
            "market_cap": int(_safe_float(_raw(price.get("marketCap")), 0.0)),
        }
    except Exception:
        return {}


def fetch_yahoo_asset_profile(symbol: str) -> dict:
    try:
        sym = urllib.parse.quote(symbol)
        url = f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{sym}?modules=assetProfile"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode())
        result = (((data or {}).get("quoteSummary") or {}).get("result") or [{}])[0]
        profile = result.get("assetProfile") or {}
        return {
            "sector": str(profile.get("sector") or "").strip(),
            "industry": str(profile.get("industry") or "").strip(),
            "business_summary": str(profile.get("longBusinessSummary") or "").strip(),
        }
    except Exception:
        return {}


def enrich_profile_for_summaries(rows: list[dict]) -> list[dict]:
    rows = list(rows or [])
    if not rows:
        return rows

    targets = []
    for r in rows:
        sec = str(r.get("sector", "N/A")).strip()
        ind = str(r.get("industry", "N/A")).strip()
        bs = str(r.get("business_summary", "")).strip()
        if sec in ("", "N/A") or ind in ("", "N/A") or not bs:
            targets.append(r)

    if not targets:
        return rows

    with ThreadPoolExecutor(max_workers=min(6, len(targets))) as ex:
        futures = {
            ex.submit(fetch_yahoo_asset_profile, str(r.get("symbol", "")).upper()): r
            for r in targets
            if r.get("symbol")
        }
        for f in as_completed(futures):
            row = futures[f]
            try:
                p = f.result() or {}
                sec = str(p.get("sector", "")).strip()
                ind = str(p.get("industry", "")).strip()
                bs = str(p.get("business_summary", "")).strip()
                if sec:
                    row["sector"] = sec
                if ind:
                    row["industry"] = ind
                if bs:
                    row["business_summary"] = bs
            except Exception:
                continue
    return rows


def enrich_result_metrics(rows: list[dict]) -> list[dict]:
    rows = list(rows or [])
    if not rows:
        return rows

    symbols = [str(r.get("symbol", "")).strip().upper() for r in rows if r.get("symbol")]
    symbols = [s for s in symbols if s]
    if not symbols:
        return rows

    # 1) 시총/이름 배치 조회
    for i in range(0, len(symbols), 150):
        chunk = symbols[i:i + 150]
        try:
            joined = urllib.parse.quote(",".join(chunk))
            url = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={joined}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode())
            by_symbol = {
                str(q.get("symbol", "")).upper(): q
                for q in (((data or {}).get("quoteResponse") or {}).get("result") or [])
            }
            for r in rows:
                s = str(r.get("symbol", "")).upper()
                q = by_symbol.get(s)
                if not q:
                    continue
                mcap = int(_safe_float(q.get("marketCap"), 0.0))
                if _safe_float(r.get("market_cap"), 0.0) <= 0 and mcap > 0:
                    r["market_cap"] = mcap
                if (not r.get("name")) or r.get("name") == s:
                    r["name"] = q.get("shortName") or q.get("longName") or r.get("name", s)
        except Exception:
            continue

    # 2) EPS/매출 성장 보강
    targets = [
        r for r in rows
        if _safe_float(r.get("eps_growth"), 0.0) == 0.0
        and _safe_float(r.get("revenue_growth"), 0.0) == 0.0
    ]
    if targets:
        with ThreadPoolExecutor(max_workers=6) as ex:
            futures = {
                ex.submit(fetch_yahoo_growth_snapshot, str(r.get("symbol", "")).upper()): r
                for r in targets
            }
            for f in as_completed(futures):
                row = futures[f]
                try:
                    g = f.result() or {}
                    if _safe_float(row.get("eps_growth"), 0.0) == 0.0 and "eps_growth" in g:
                        row["eps_growth"] = round(_safe_float(g.get("eps_growth"), 0.0), 1)
                    if _safe_float(row.get("revenue_growth"), 0.0) == 0.0 and "revenue_growth" in g:
                        row["revenue_growth"] = round(_safe_float(g.get("revenue_growth"), 0.0), 1)
                    if _safe_float(row.get("market_cap"), 0.0) <= 0 and _safe_float(g.get("market_cap"), 0.0) > 0:
                        row["market_cap"] = int(_safe_float(g.get("market_cap"), 0.0))
                except Exception:
                    continue

    return rows
