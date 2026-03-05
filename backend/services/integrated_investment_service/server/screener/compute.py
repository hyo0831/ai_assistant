from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from fastapi import HTTPException

from .models import ScreenerRequest


class ComputeDeps(Protocol):
    def safe_float(self, value, default=0.0): ...
    def get_us_index_universe(self) -> set[str]: ...
    def get_sp500_symbols(self) -> set[str]: ...
    def collect_snapshots_throttled(self, **kwargs) -> dict[str, dict]: ...
    def percentile_rank(self, values: list[float], current: float) -> float: ...
    def dedupe_rows(self, rows: list[dict]) -> tuple[list[dict], int]: ...
    def sort_rows(self, rows: list[dict], sort_by: str) -> list[dict]: ...
    def deep_canslim_snapshot(self, symbol: str, provider: str) -> dict | None: ...
    def enrich_result_metrics(self, rows: list[dict]) -> list[dict]: ...
    def attach_summaries(self, rows: list[dict], provider: str) -> list[dict]: ...


def compute_screener(
    req: ScreenerRequest,
    deps: ComputeDeps,
    *,
    default_provider: str,
    phase1_workers: int,
    phase2_workers: int,
    batch_size: int,
    batch_pause_sec: float,
) -> dict:
    if req.market.upper() != "US":
        raise HTTPException(status_code=400, detail="현재는 US 시장만 지원합니다.")

    sort_by = req.sort_by.strip().lower()
    allowed_sort = {"score", "ai_score", "rs", "eps_growth", "revenue_growth", "from_high"}
    if sort_by not in allowed_sort:
        sort_by = "score"

    max_results = max(1, min(int(req.max_results), 100))
    min_market_cap = float(req.min_market_cap)
    prefilter_count = max(120, min(int(req.prefilter_count), 300))
    ai_rerank_count = max(20, min(int(req.ai_rerank_count), 100))
    provider = (req.provider or default_provider).strip().lower()
    if provider not in ("gemini", "openai", "claude"):
        provider = default_provider

    try:
        import yfinance as yf
    except Exception:
        raise HTTPException(status_code=500, detail="yfinance 의존성이 설치되지 않았습니다.")

    symbols = sorted(deps.get_us_index_universe())
    sp500_symbols = deps.get_sp500_symbols()
    if not symbols:
        raise HTTPException(status_code=500, detail="스크리너 유니버스를 구성하지 못했습니다.")

    benchmark_hist = yf.Ticker("^GSPC").history(period="1y", interval="1d", auto_adjust=False)
    if benchmark_hist is None or benchmark_hist.empty:
        raise HTTPException(status_code=500, detail="벤치마크 데이터를 불러오지 못했습니다.")
    bclose = benchmark_hist["Close"].dropna()
    if len(bclose) < 120:
        raise HTTPException(status_code=500, detail="벤치마크 데이터가 충분하지 않습니다.")
    b_now = deps.safe_float(bclose.iloc[-1], 0.0)
    b_6m = deps.safe_float(bclose.iloc[max(0, len(bclose) - 126)], 0.0)
    b_12m = deps.safe_float(bclose.iloc[0], 0.0)
    bench_6m = ((b_now / b_6m) - 1.0) if b_6m > 0 else 0.0
    bench_12m = ((b_now / b_12m) - 1.0) if b_12m > 0 else 0.0

    phase1_map = deps.collect_snapshots_throttled(
        symbols=symbols,
        bench_6m=bench_6m,
        bench_12m=bench_12m,
        include_info=False,
        workers=phase1_workers,
        batch_size=batch_size,
        pause_sec=batch_pause_sec,
    )
    snapshots = list(phase1_map.values())

    if not snapshots:
        raise HTTPException(status_code=500, detail="종목 데이터를 불러오지 못했습니다.")

    rs_values = [s["rs_raw"] for s in snapshots]
    ranked = []
    for s in snapshots:
        rs_score = deps.percentile_rank(rs_values, s["rs_raw"])
        s["rs_score"] = round(rs_score, 1)

        fh = max(0.0, min(100.0, s["from_high_pct"]))
        eps_n = max(0.0, min(100.0, 50.0 + s["eps_growth"] * 1.2))
        rev_n = max(0.0, min(100.0, 50.0 + s["revenue_growth"] * 1.0))
        vol_n = max(0.0, min(100.0, s["vol_ratio"] * 40.0))
        score = fh * 0.35 + rs_score * 0.35 + eps_n * 0.20 + rev_n * 0.05 + vol_n * 0.05
        s["score"] = round(score, 1)
        ranked.append(s)

    ranked, _ = deps.dedupe_rows(ranked)
    ranked = deps.sort_rows(ranked, "score")

    candidate_n = max(prefilter_count, max_results * 2, ai_rerank_count * 2)
    candidates = ranked[:min(candidate_n, len(ranked))]
    enriched_map = deps.collect_snapshots_throttled(
        symbols=[row["symbol"] for row in candidates],
        bench_6m=bench_6m,
        bench_12m=bench_12m,
        include_info=True,
        workers=phase2_workers,
        batch_size=max(20, batch_size // 2),
        pause_sec=max(0.8, batch_pause_sec),
    )

    filtered = []
    for row in candidates:
        symbol = row["symbol"]
        info_row = enriched_map.get(symbol)
        if info_row:
            row["name"] = info_row.get("name", row.get("name", symbol))
            row["sector"] = info_row.get("sector", row.get("sector", "N/A"))
            row["industry"] = info_row.get("industry", row.get("industry", "N/A"))
            row["market_cap"] = info_row.get("market_cap", row.get("market_cap", 0))
            row["eps_growth"] = info_row.get("eps_growth", row.get("eps_growth", 0))
            row["revenue_growth"] = info_row.get("revenue_growth", row.get("revenue_growth", 0))
        mcap = deps.safe_float(row.get("market_cap"), 0.0)
        is_sp500 = symbol in sp500_symbols
        if mcap < min_market_cap and not is_sp500:
            continue
        filtered.append(row)

    filtered, _ = deps.dedupe_rows(filtered)
    filtered = deps.sort_rows(filtered, "score")
    preselected = filtered[:prefilter_count]

    deep_n = min(len(preselected), max(max_results, ai_rerank_count))
    deep_targets = preselected[:deep_n]
    deep_map = {}
    if deep_targets:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        with ThreadPoolExecutor(max_workers=min(4, deep_n)) as ex:
            futures = {
                ex.submit(deps.deep_canslim_snapshot, row["symbol"], provider): row["symbol"]
                for row in deep_targets
            }
            for f in as_completed(futures):
                symbol = futures[f]
                try:
                    detail = f.result()
                    if detail:
                        deep_map[symbol] = detail
                except Exception:
                    continue

    for row in preselected:
        deep = deep_map.get(row["symbol"])
        if deep:
            row["ai_score"] = int(deep.get("ai_score", row["score"]))
            row["score"] = row["ai_score"]
            row["ai_reason"] = deep.get("ai_reason", "")
            row["name"] = deep.get("name", row.get("name", row["symbol"]))
            row["sector"] = deep.get("sector", row.get("sector", "N/A"))
            row["industry"] = deep.get("industry", row.get("industry", "N/A"))
            row["deep"] = deep
            chart = deep.get("chart", {})
            row["chart_pattern"] = chart.get("best_pattern")
            row["pattern_quality"] = chart.get("pattern_quality")
            row["canslim_rs_rating"] = chart.get("rs_rating")
        else:
            row["ai_score"] = int(row.get("score", 0))
            row["ai_reason"] = "AI 재평가 미적용(정량 점수 사용)"

    preselected = deps.sort_rows(preselected, sort_by)
    preselected, dup_removed = deps.dedupe_rows(preselected)
    results = preselected[:max_results]
    results = deps.enrich_result_metrics(results)
    for row in results:
        row["summary"] = str(row.get("summary", "") or "")
        row["industry"] = str(row.get("industry", "N/A") or "N/A")
    results = deps.attach_summaries(results, provider=provider)
    analyzed_at = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()

    return {
        "market": "US",
        "universe": "S&P500 + NASDAQ (all)",
        "universe_size": len(symbols),
        "scanned": len(snapshots),
        "matched": len(filtered),
        "filter_basis": "market_cap_only",
        "provider": provider,
        "prefilter_count": prefilter_count,
        "ai_rerank_count": deep_n,
        "ai_scored_count": len(deep_map),
        "duplicates_removed": dup_removed,
        "analyzed_at": analyzed_at,
        "results": results,
        "timestamp": datetime.utcnow().isoformat(),
    }
