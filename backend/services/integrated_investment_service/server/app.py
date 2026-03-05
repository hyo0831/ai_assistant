from __future__ import annotations

"""
O'Neil AI 투자 어시스턴트 — 통합 FastAPI 서버
트레이딩 모드(trading/) + 분석 모드(src/)를 하나의 API로 제공
백엔드 루트: backend/services/integrated_investment_service/
"""

import os
import sys
import base64
import tempfile
import re
import time
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Optional
from dotenv import load_dotenv
import threading
import json as json_mod
from server.screener.models import ScreenerRequest, ScreenerRefreshRequest
from server.screener.routes import create_screener_router
from server.screener.service import ScreenerService
from server.screener.compute import compute_screener as screener_compute
from server.screener.store import (
    ScreenerCacheStore,
    load_json_file as screener_load_json_file,
    save_json_file as screener_save_json_file,
)
from server.screener import data_sources as screener_data_sources

# 프로젝트 루트 = backend/services/integrated_investment_service/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
TRADING_DIR = PROJECT_ROOT / "trading"
REPO_ROOT = PROJECT_ROOT.parent.parent.parent

# .env 로드
load_dotenv(PROJECT_ROOT / ".env")

# sys.path 설정
# - PROJECT_ROOT: from src.analyzer import ... (분석 모드)
# - TRADING_DIR: from core.data_fetcher import ... (트레이딩 모드)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(TRADING_DIR) not in sys.path:
    sys.path.insert(0, str(TRADING_DIR))

# 필요한 디렉토리 미리 생성
for d in [TRADING_DIR / "results", TRADING_DIR / "feedback",
          PROJECT_ROOT / "results"]:
    d.mkdir(parents=True, exist_ok=True)


# ── numpy/pandas 직렬화 헬퍼 ───────────────────────
def convert_numpy(obj):
    try:
        import numpy as np
        if isinstance(obj, dict):
            return {k: convert_numpy(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_numpy(i) for i in obj]
        elif isinstance(obj, (np.bool_,)):
            return bool(obj)
        elif isinstance(obj, (np.integer,)):
            return int(obj)
        elif isinstance(obj, (np.floating,)):
            v = float(obj)
            if v != v:
                return None
            return v
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
    except ImportError:
        pass
    if isinstance(obj, float) and obj != obj:
        return None
    return obj


# ── FastAPI 앱 설정 ─────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[WARNING] GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")
    else:
        print(f"[OK] GEMINI_API_KEY 확인됨 (길이: {len(api_key)})")
    print("[OK] O'Neil AI 통합 서버 시작")
    print(f"  - 프로젝트 루트: {PROJECT_ROOT}")
    print(f"  - 트레이딩 모듈: {TRADING_DIR}")
    yield
    print("[OK] 서버 종료")


app = FastAPI(
    title="O'Neil AI Investment Assistant",
    description="CAN SLIM 트레이딩 모드 + 펀더멘털 분석 모드 통합 API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 에러 핸들러 ─────────────────────────────────────
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers={"Access-Control-Allow-Origin": "*"},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": f"서버 내부 오류: {str(exc)}"},
        headers={"Access-Control-Allow-Origin": "*"},
    )


# ── Request/Response 모델 ───────────────────────────
class TradingRequest(BaseModel):
    ticker: str = Field(..., description="종목 코드", examples=["AAPL"])
    mode: str = Field(default="v2", description="분석 모드: v1 또는 v2")
    interval: str = Field(default="1wk", description="차트 간격: 1wk 또는 1d")
    provider: str = Field(default="gemini", description="AI 제공자: gemini/openai/claude")


class TradingResponse(BaseModel):
    ticker: str
    mode: str
    analysis: str
    pattern_data: Optional[dict] = None
    chart_base64: Optional[str] = None
    timestamp: str


class AnalysisRequest(BaseModel):
    ticker: str = Field(..., description="종목 코드", examples=["AAPL", "005930.KS"])
    provider: str = Field(default="gemini", description="AI 제공자: gemini/openai/claude")


class AnalysisResponse(BaseModel):
    ticker: str
    company_name: str = ""
    currency: str = "USD"
    summary: dict = {}
    ai_analysis: str = ""
    fundamental_data: dict = {}
    timestamp: str = ""


class HealthResponse(BaseModel):
    status: str
    version: str
    modes: list[str]


SCREENER_CACHE_FILE = PROJECT_ROOT / "screener_cache.json"
SCREENER_UNIVERSE_FILE = PROJECT_ROOT / "screener_universe_cache.json"
SCREENER_SNAPSHOT_FILE = PROJECT_ROOT / "screener_snapshot_store.json"
SCREENER_DATASET_FILE = PROJECT_ROOT / "screener_precomputed_dataset.json"
SCREENER_CACHE_LOCK = threading.Lock()
SCREENER_DEFAULT_MARKET = "US"
SCREENER_DEFAULT_MIN_MARKET_CAP = 500_000_000.0
SCREENER_DEFAULT_PROVIDER = "claude"
SCREENER_REFRESH_POLICY = "매주 월요일 오전 9시(KST) 갱신"
SCREENER_PHASE1_WORKERS = int(os.environ.get("SCREENER_PHASE1_WORKERS", "4"))
SCREENER_PHASE2_WORKERS = int(os.environ.get("SCREENER_PHASE2_WORKERS", "1"))
SCREENER_BATCH_SIZE = int(os.environ.get("SCREENER_BATCH_SIZE", "80"))
SCREENER_BATCH_PAUSE_SEC = float(os.environ.get("SCREENER_BATCH_PAUSE_SEC", "0.5"))
SCREENER_SUMMARY_WORKERS = int(os.environ.get("SCREENER_SUMMARY_WORKERS", "4"))
SCREENER_SUMMARY_MAX_CHARS = int(os.environ.get("SCREENER_SUMMARY_MAX_CHARS", "80"))
SCREENER_SUMMARY_SYNC_FILL = int(os.environ.get("SCREENER_SUMMARY_SYNC_FILL", "3"))
SCREENER_METRICS_REFRESH_BATCH = int(os.environ.get("SCREENER_METRICS_REFRESH_BATCH", "20"))
SCREENER_UNIVERSE_TTL_DAYS = int(os.environ.get("SCREENER_UNIVERSE_TTL_DAYS", "90"))
SCREENER_REFRESH_STATE_LOCK = threading.Lock()
SCREENER_REFRESH_STATE = {
    "running": False,
    "started_at": None,
    "finished_at": None,
    "status": "idle",  # idle|running|success|error
    "error": "",
    "result_count": 0,
    "provider": SCREENER_DEFAULT_PROVIDER,
}
SCREENER_SUMMARY_BACKFILL_LOCK = threading.Lock()
SCREENER_SUMMARY_BACKFILL_RUNNING = False
_SCREENER_CACHE_STORE = ScreenerCacheStore(SCREENER_CACHE_FILE)


def _load_screener_cache() -> Optional[dict]:
    return _SCREENER_CACHE_STORE.load()


def _save_screener_cache(payload: dict):
    _SCREENER_CACHE_STORE.save(payload)


def _load_json_file(path: Path) -> Optional[dict]:
    return screener_load_json_file(path)


def _save_json_file(path: Path, payload: dict):
    screener_save_json_file(path, payload)


def _get_cached_universe_symbols() -> list[str]:
    now = datetime.utcnow().replace(tzinfo=timezone.utc)
    cache = _load_json_file(SCREENER_UNIVERSE_FILE) or {}
    symbols = list(cache.get("symbols", []) or [])
    fetched_at_raw = cache.get("fetched_at")
    if symbols and fetched_at_raw:
        try:
            fetched_at = datetime.fromisoformat(str(fetched_at_raw).replace("Z", "+00:00"))
            age_days = (now - fetched_at).total_seconds() / 86400.0
            if age_days <= max(1, SCREENER_UNIVERSE_TTL_DAYS):
                return sorted({str(s).upper() for s in symbols if s})
        except Exception:
            pass

    symbols = sorted(_get_us_index_universe())
    payload = {
        "fetched_at": now.isoformat(),
        "ttl_days": SCREENER_UNIVERSE_TTL_DAYS,
        "symbols": symbols,
    }
    _save_json_file(SCREENER_UNIVERSE_FILE, payload)
    return symbols


def _load_snapshot_store() -> dict:
    data = _load_json_file(SCREENER_SNAPSHOT_FILE) or {}
    return {
        "updated_at": data.get("updated_at"),
        "cursor": int(_safe_float(data.get("cursor"), 0)),
        "items": data.get("items", {}) if isinstance(data.get("items"), dict) else {},
    }


def _save_snapshot_store(store: dict):
    payload = {
        "updated_at": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat(),
        "cursor": int(_safe_float(store.get("cursor"), 0)),
        "items": store.get("items", {}),
    }
    _save_json_file(SCREENER_SNAPSHOT_FILE, payload)


def _build_precomputed_dataset_from_snapshot(provider: str) -> dict:
    store = _load_snapshot_store()
    items = store.get("items", {}) or {}
    rows = []
    for symbol, row in items.items():
        r = dict(row or {})
        r["symbol"] = str(symbol).upper()
        r["name"] = r.get("name") or r["symbol"]
        r["sector"] = r.get("sector") or "N/A"
        r["industry"] = r.get("industry") or "N/A"
        r["price"] = round(_safe_float(r.get("price"), 0.0), 2)
        r["from_high_pct"] = round(_safe_float(r.get("from_high_pct"), 0.0), 1)
        r["eps_growth"] = round(_safe_float(r.get("eps_growth"), 0.0), 1)
        r["revenue_growth"] = round(_safe_float(r.get("revenue_growth"), 0.0), 1)
        r["vol_ratio"] = round(_safe_float(r.get("vol_ratio"), 1.0), 2)
        r["market_cap"] = int(_safe_float(r.get("market_cap"), 0.0))
        r["rs_raw"] = round(_safe_float(r.get("rs_raw"), 0.0), 4)
        r["summary"] = str(r.get("summary", "") or "")
        rows.append(r)

    if not rows:
        payload = {
            "provider": provider,
            "analyzed_at": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat(),
            "results": [],
            "dataset_size": 0,
            "refresh_policy": SCREENER_REFRESH_POLICY,
            "timestamp": datetime.utcnow().isoformat(),
        }
        _save_json_file(SCREENER_DATASET_FILE, payload)
        return payload

    rs_values = [_safe_float(r.get("rs_raw"), 0.0) for r in rows]
    for r in rows:
        rs_score = _percentile_rank(rs_values, _safe_float(r.get("rs_raw"), 0.0))
        r["rs_score"] = round(rs_score, 1)
        fh = max(0.0, min(100.0, _safe_float(r.get("from_high_pct"), 0.0)))
        eps_n = max(0.0, min(100.0, 50.0 + _safe_float(r.get("eps_growth"), 0.0) * 1.2))
        rev_n = max(0.0, min(100.0, 50.0 + _safe_float(r.get("revenue_growth"), 0.0) * 1.0))
        vol_n = max(0.0, min(100.0, _safe_float(r.get("vol_ratio"), 1.0) * 40.0))
        score = fh * 0.35 + rs_score * 0.35 + eps_n * 0.20 + rev_n * 0.05 + vol_n * 0.05
        r["score"] = round(score, 1)
        r["ai_score"] = int(round(score))
        r["ai_reason"] = r.get("ai_reason") or "정량 점수 기반"

    rows = _sort_screener_rows(rows, "score")
    top_for_summary = rows[:120]
    missing = [r for r in top_for_summary if not str(r.get("summary", "")).strip()]
    if missing:
        _attach_investor_summaries(missing, provider=provider)

    payload = {
        "provider": provider,
        "analyzed_at": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat(),
        "dataset_size": len(rows),
        "results": rows,
        "refresh_policy": SCREENER_REFRESH_POLICY,
        "timestamp": datetime.utcnow().isoformat(),
    }
    _save_json_file(SCREENER_DATASET_FILE, payload)
    return payload


def _refresh_snapshot_batch(provider: str, batch_size: int = 20) -> tuple[int, int]:
    provider = (provider or SCREENER_DEFAULT_PROVIDER).lower().strip()
    symbols = _get_cached_universe_symbols()
    if not symbols:
        return 0, 0
    store = _load_snapshot_store()
    items = store.get("items", {}) or {}
    total = len(symbols)
    batch_size = max(1, min(int(batch_size), total))
    cursor = max(0, min(int(_safe_float(store.get("cursor"), 0)), max(0, total - 1)))
    selected = [symbols[(cursor + i) % total] for i in range(batch_size)]

    try:
        import yfinance as yf
        bench_hist = yf.Ticker("^GSPC").history(period="1y", interval="1d", auto_adjust=False)
        bclose = bench_hist["Close"].dropna()
        b_now = _safe_float(bclose.iloc[-1], 0.0) if len(bclose) else 0.0
        b_6m = _safe_float(bclose.iloc[max(0, len(bclose) - 126)], 0.0) if len(bclose) else 0.0
        b_12m = _safe_float(bclose.iloc[0], 0.0) if len(bclose) else 0.0
        bench_6m = ((b_now / b_6m) - 1.0) if b_6m > 0 else 0.0
        bench_12m = ((b_now / b_12m) - 1.0) if b_12m > 0 else 0.0
    except Exception:
        bench_6m = 0.0
        bench_12m = 0.0

    fetched = _collect_snapshots_throttled(
        symbols=selected,
        bench_6m=bench_6m,
        bench_12m=bench_12m,
        include_info=True,
        workers=max(1, min(SCREENER_PHASE2_WORKERS, 2)),
        batch_size=max(10, min(batch_size, 30)),
        pause_sec=max(0.4, SCREENER_BATCH_PAUSE_SEC),
    )
    refreshed_rows = list(fetched.values())
    refreshed_rows = _enrich_result_metrics(refreshed_rows)
    refreshed_rows = _attach_investor_summaries(refreshed_rows, provider=provider)

    updated = 0
    for row in refreshed_rows:
        sym = str(row.get("symbol", "")).upper()
        if not sym:
            continue
        before = items.get(sym, {})
        b_sig = (
            _safe_float(before.get("market_cap"), 0.0),
            _safe_float(before.get("eps_growth"), 0.0),
            _safe_float(before.get("revenue_growth"), 0.0),
            str(before.get("summary", "") or ""),
        )
        merged = dict(before)
        for k, v in row.items():
            if k in ("market_cap", "eps_growth", "revenue_growth", "price", "from_high_pct", "vol_ratio", "rs_raw"):
                vv = _safe_float(v, 0.0)
                if vv != 0.0 or k in ("price", "from_high_pct", "vol_ratio", "rs_raw"):
                    merged[k] = int(vv) if k == "market_cap" else round(vv, 4)
            elif k in ("name", "sector", "industry", "summary"):
                if str(v or "").strip():
                    merged[k] = v
            else:
                merged[k] = v
        items[sym] = merged
        a_sig = (
            _safe_float(merged.get("market_cap"), 0.0),
            _safe_float(merged.get("eps_growth"), 0.0),
            _safe_float(merged.get("revenue_growth"), 0.0),
            str(merged.get("summary", "") or ""),
        )
        if a_sig != b_sig:
            updated += 1

    store["items"] = items
    store["cursor"] = (cursor + batch_size) % total
    _save_snapshot_store(store)
    _build_precomputed_dataset_from_snapshot(provider=provider)
    return len(refreshed_rows), updated


def _refresh_state_snapshot() -> dict:
    with SCREENER_REFRESH_STATE_LOCK:
        return dict(SCREENER_REFRESH_STATE)


def _set_refresh_state(**kwargs):
    with SCREENER_REFRESH_STATE_LOCK:
        for k, v in kwargs.items():
            if k in SCREENER_REFRESH_STATE:
                SCREENER_REFRESH_STATE[k] = v


def _build_refresh_scan_request(provider: str, min_market_cap: float, max_results: int) -> ScreenerRequest:
    return ScreenerRequest(
        market="US",
        min_market_cap=min_market_cap,
        sort_by="score",
        max_results=max_results,
        provider=provider,
        prefilter_count=max(160, max_results + 60),
        ai_rerank_count=0,
        use_cache=False,
        force_refresh=True,
    )


def _bootstrap_screener_cache_fast(scan_req: ScreenerRequest) -> dict:
    seed = [
        "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "COST", "NFLX",
        "AMD", "ADBE", "CSCO", "PEP", "QCOM", "AMGN", "INTU", "AMAT", "BKNG", "ISRG",
        "JPM", "V", "MA", "UNH", "XOM", "LLY", "WMT", "JNJ", "PG", "CAT",
    ]
    max_results = max(1, min(int(scan_req.max_results), len(seed)))
    rows = []
    for i, sym in enumerate(seed[:max_results]):
        rows.append({
            "symbol": sym,
            "name": sym,
            "sector": "N/A",
            "industry": "N/A",
            "price": 0.0,
            "from_high_pct": 0.0,
            "eps_growth": 0.0,
            "revenue_growth": 0.0,
            "vol_ratio": 1.0,
            "market_cap": 0,
            "rs_score": 50.0,
            "score": max(40, 80 - i),
            "ai_score": max(40, 80 - i),
            "ai_reason": "초기 캐시 부트스트랩",
            "summary": "",
        })

    rows = _enrich_result_metrics(rows)
    rows = _attach_investor_summaries(rows, provider=scan_req.provider)
    analyzed_at = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
    return {
        "market": "US",
        "universe": "bootstrap_seed",
        "universe_size": len(seed),
        "scanned": len(rows),
        "matched": len(rows),
        "filter_basis": "bootstrap",
        "provider": scan_req.provider,
        "prefilter_count": len(rows),
        "ai_rerank_count": 0,
        "ai_scored_count": 0,
        "duplicates_removed": 0,
        "analyzed_at": analyzed_at,
        "results": rows,
        "metrics_refresh_batch": min(SCREENER_METRICS_REFRESH_BATCH, len(rows)),
        "metrics_refresh_cursor": 0,
        "timestamp": datetime.utcnow().isoformat(),
    }


def _refresh_cached_metrics_incremental(scan_req: ScreenerRequest) -> tuple[bool, int]:
    cache = _load_screener_cache() or {}
    rows = list(cache.get("results", []))
    if not rows:
        return False, 0

    total = len(rows)
    batch = max(1, min(SCREENER_METRICS_REFRESH_BATCH, total))
    cursor = int(_safe_float(cache.get("metrics_refresh_cursor", 0), 0))
    cursor = max(0, min(cursor, total - 1))

    selected = []
    indexes = []
    for i in range(batch):
        idx = (cursor + i) % total
        indexes.append(idx)
        selected.append(dict(rows[idx]))

    refreshed = _enrich_result_metrics(selected)
    refreshed = _attach_investor_summaries(refreshed, provider=scan_req.provider)

    updated = 0
    for idx, new_row in zip(indexes, refreshed):
        base = rows[idx]
        before = (
            _safe_float(base.get("market_cap"), 0.0),
            _safe_float(base.get("eps_growth"), 0.0),
            _safe_float(base.get("revenue_growth"), 0.0),
            str(base.get("summary", "") or ""),
        )
        for k in ("name", "sector", "industry", "summary"):
            if k in new_row and str(new_row.get(k, "")).strip():
                base[k] = new_row[k]
        for k in ("market_cap", "eps_growth", "revenue_growth"):
            nv = _safe_float(new_row.get(k), 0.0)
            if nv != 0.0:
                base[k] = int(nv) if k == "market_cap" else round(nv, 1)
        after = (
            _safe_float(base.get("market_cap"), 0.0),
            _safe_float(base.get("eps_growth"), 0.0),
            _safe_float(base.get("revenue_growth"), 0.0),
            str(base.get("summary", "") or ""),
        )
        if before != after:
            updated += 1

    cache["results"] = rows
    cache["analyzed_at"] = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
    cache["timestamp"] = datetime.utcnow().isoformat()
    cache["metrics_refresh_batch"] = batch
    cache["metrics_refresh_cursor"] = (cursor + batch) % total
    _save_screener_cache(cache)
    return True, updated


def _run_screener_refresh_job(scan_req: ScreenerRequest):
    started_at = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
    _set_refresh_state(
        running=True,
        started_at=started_at,
        finished_at=None,
        status="running",
        error="",
        result_count=0,
        provider=scan_req.provider,
    )
    try:
        cache = _load_screener_cache()
        used_incremental, updated_count = _refresh_cached_metrics_incremental(scan_req)
        if used_incremental:
            data = _load_screener_cache() or {}
        elif not cache:
            data = _bootstrap_screener_cache_fast(scan_req)
            _save_screener_cache(data)
        else:
            data = _compute_screener(scan_req)
            _save_screener_cache(data)
        _set_refresh_state(
            running=False,
            finished_at=datetime.utcnow().replace(tzinfo=timezone.utc).isoformat(),
            status="success",
            error="",
            result_count=len(data.get("results", [])),
        )
        if used_incremental:
            print(f"[OK] incremental metrics refresh done: updated={updated_count}, total={len(data.get('results', []))}")
    except Exception as exc:
        _set_refresh_state(
            running=False,
            finished_at=datetime.utcnow().replace(tzinfo=timezone.utc).isoformat(),
            status="error",
            error=str(exc),
        )
        print(f"[WARN] screener refresh job failed: {exc}")


def _start_screener_refresh(scan_req: ScreenerRequest) -> bool:
    with SCREENER_REFRESH_STATE_LOCK:
        if SCREENER_REFRESH_STATE.get("running"):
            return False
        SCREENER_REFRESH_STATE["running"] = True
        SCREENER_REFRESH_STATE["status"] = "running"
        SCREENER_REFRESH_STATE["started_at"] = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
        SCREENER_REFRESH_STATE["finished_at"] = None
        SCREENER_REFRESH_STATE["error"] = ""
        SCREENER_REFRESH_STATE["result_count"] = 0
        SCREENER_REFRESH_STATE["provider"] = scan_req.provider

    t = threading.Thread(target=_run_screener_refresh_job, args=(scan_req,), daemon=True)
    t.start()
    return True


def _run_cache_summary_backfill(provider: str, max_rows: int):
    global SCREENER_SUMMARY_BACKFILL_RUNNING
    try:
        cache = _load_screener_cache() or {}
        rows = list(cache.get("results", []))
        if not rows:
            return
        max_rows = max(1, min(int(max_rows), len(rows)))
        targets = rows[:max_rows]
        missing = [r for r in targets if not str(r.get("summary", "")).strip()]
        if not missing:
            return
        _attach_investor_summaries(missing, provider=provider)
        cache["results"] = rows
        _save_screener_cache(cache)
    except Exception as exc:
        print(f"[WARN] cache summary backfill failed: {exc}")
    finally:
        with SCREENER_SUMMARY_BACKFILL_LOCK:
            SCREENER_SUMMARY_BACKFILL_RUNNING = False


def _start_cache_summary_backfill(provider: str, max_rows: int) -> bool:
    global SCREENER_SUMMARY_BACKFILL_RUNNING
    with SCREENER_SUMMARY_BACKFILL_LOCK:
        if SCREENER_SUMMARY_BACKFILL_RUNNING:
            return False
        SCREENER_SUMMARY_BACKFILL_RUNNING = True
    t = threading.Thread(
        target=_run_cache_summary_backfill,
        args=(provider, max_rows),
        daemon=True,
    )
    t.start()
    return True


def _is_default_cache_request(req: ScreenerRequest) -> bool:
    return (
        req.market.upper() == SCREENER_DEFAULT_MARKET
        and abs(float(req.min_market_cap) - SCREENER_DEFAULT_MIN_MARKET_CAP) < 1
        and (req.provider or SCREENER_DEFAULT_PROVIDER).lower() == SCREENER_DEFAULT_PROVIDER
    )


def _sort_screener_rows(rows: list[dict], sort_by: str) -> list[dict]:
    rows = list(rows or [])
    sort_by = (sort_by or "score").lower()
    sort_map = {
        "score": "ai_score",
        "ai_score": "ai_score",
        "rs": "rs_score",
        "eps_growth": "eps_growth",
        "revenue_growth": "revenue_growth",
        "from_high": "from_high_pct",
    }
    key = sort_map.get(sort_by, "ai_score")
    rows.sort(key=lambda x: _safe_float(x.get(key, x.get("score")), 0.0), reverse=True)
    return rows


def _dedupe_rows(rows: list[dict]) -> tuple[list[dict], int]:
    seen = set()
    out = []
    dup = 0
    for r in rows:
        symbol = str(r.get("symbol", "")).upper().strip()
        if not symbol:
            continue
        if symbol in seen:
            dup += 1
            continue
        seen.add(symbol)
        out.append(r)
    return out, dup


def _safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _chunked(seq: list, size: int):
    if size <= 0:
        size = 1
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def _percentile_rank(values: list[float], current: float) -> float:
    if not values:
        return 50.0
    smaller_or_equal = sum(1 for v in values if v <= current)
    return round((smaller_or_equal / len(values)) * 100.0, 1)


def _get_us_index_universe() -> set[str]:
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

        # S&P500 raw 템플릿: {{NyseSymbol|MMM}}, {{NasdaqSymbol|ADBE}}
        sp500_symbols = {
            m.group(1).strip().upper().replace(".", "-")
            for m in re.finditer(r"\|\{\{(?:NyseSymbol|NasdaqSymbol)\|([A-Za-z0-9\.\-]+)", sp_raw)
        }

        # Nasdaq 전체 목록 (nasdaqtraded.txt)
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
            # "나스닥 전체" = NASDAQ 상장 종목(Q)
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


def _get_sp500_symbols() -> set[str]:
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


def _fetch_symbol_snapshot(symbol: str, bench_6m: float, bench_12m: float, include_info: bool = False):
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


def _collect_snapshots_throttled(
    symbols: list[str],
    bench_6m: float,
    bench_12m: float,
    include_info: bool,
    workers: int,
    batch_size: int,
    pause_sec: float,
) -> dict[str, dict]:
    """느린 배치 스캔: 대유니버스 호출량을 분산해 rate limit를 완화."""
    workers = max(1, workers)
    batch_size = max(1, batch_size)
    out = {}
    for chunk in _chunked(symbols, batch_size):
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {
                ex.submit(_fetch_symbol_snapshot, sym, bench_6m, bench_12m, include_info): sym
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


def _fetch_yahoo_growth_snapshot(symbol: str) -> dict:
    return screener_data_sources.fetch_yahoo_growth_snapshot(symbol)


def _fetch_yahoo_asset_profile(symbol: str) -> dict:
    return screener_data_sources.fetch_yahoo_asset_profile(symbol)


def _enrich_profile_for_summaries(rows: list[dict]) -> list[dict]:
    return screener_data_sources.enrich_profile_for_summaries(rows)


def _enrich_result_metrics(rows: list[dict]) -> list[dict]:
    return screener_data_sources.enrich_result_metrics(rows)


def _heuristic_canslim_score(detail: dict) -> int:
    chart = detail.get("chart", {})
    c = detail.get("C", {})
    a = detail.get("A", {})
    s = detail.get("S", {})
    n = detail.get("N", {})

    rs = _safe_float(chart.get("rs_rating"), 50.0)
    pattern_quality = _safe_float(chart.get("pattern_quality"), 0.0)
    from_high = _safe_float(n.get("from_high_pct"), 50.0)
    c_latest = _safe_float(c.get("latest_eps_yoy"), 0.0)
    c_rev = _safe_float(c.get("revenue_growth"), 0.0)
    a_cons = _safe_float(a.get("consecutive_growth_years"), 0.0)
    a_roe = _safe_float(a.get("roe"), 0.0)
    debt = _safe_float(s.get("debt_to_equity"), 100.0)
    buyback = 1.0 if s.get("buyback_detected") else 0.0
    catalyst = 1.0 if n.get("has_meaningful_catalyst") else 0.0

    debt_norm = max(0.0, min(100.0, 100.0 - debt * 0.5))
    score = (
        rs * 0.28
        + pattern_quality * 0.20
        + from_high * 0.16
        + max(0.0, min(100.0, 50.0 + c_latest * 1.2)) * 0.14
        + max(0.0, min(100.0, 50.0 + c_rev * 1.0)) * 0.08
        + max(0.0, min(100.0, a_cons * 18.0 + min(a_roe, 40.0))) * 0.08
        + debt_norm * 0.03
        + (buyback * 100.0) * 0.01
        + (catalyst * 100.0) * 0.02
    )
    return max(0, min(99, int(round(score))))


def _ai_score_candidate(detail: dict, provider: str) -> tuple[int, str]:
    provider = (provider or "gemini").lower()
    prompt = (
        "You are a strict William O'Neil CAN SLIM quant-style scorer.\n"
        "Score this stock from 0 to 99 based on chart + C/A/S/N evidence.\n"
        "Important: output must be ONLY JSON.\n"
        "Format: {\"score\": 0-99, \"reason\": \"one short sentence\"}\n\n"
        f"DATA:\n{json_mod.dumps(detail, ensure_ascii=False)}"
    )

    try:
        if provider == "gemini":
            if not os.environ.get("GEMINI_API_KEY"):
                raise ValueError("missing GEMINI_API_KEY")
            from google import genai
            client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
            resp = client.models.generate_content(
                model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
                contents=prompt,
            )
            text = (resp.text or "").strip()
        elif provider == "openai":
            if not os.environ.get("OPENAI_API_KEY"):
                raise ValueError("missing OPENAI_API_KEY")
            from openai import OpenAI
            client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
            resp = client.chat.completions.create(
                model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
                messages=[
                    {"role": "system", "content": "Return only strict JSON."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
            )
            text = (resp.choices[0].message.content or "").strip()
        elif provider == "claude":
            if not os.environ.get("ANTHROPIC_API_KEY"):
                raise ValueError("missing ANTHROPIC_API_KEY")
            from anthropic import Anthropic
            client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
            resp = client.messages.create(
                model=os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
                max_tokens=500,
                system="Return only strict JSON.",
                messages=[{"role": "user", "content": prompt}],
            )
            text = "".join(
                block.text for block in resp.content if getattr(block, "type", "") == "text"
            ).strip()
        else:
            raise ValueError(f"unsupported provider: {provider}")

        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        obj = json_mod.loads(text)
        score = int(_safe_float(obj.get("score"), 0))
        reason = str(obj.get("reason") or "").strip()
        score = max(0, min(99, score))
        if not reason:
            reason = "AI 점수 산출"
        return score, reason
    except Exception as exc:
        fallback = _heuristic_canslim_score(detail)
        return fallback, f"AI 점수 실패로 휴리스틱 사용: {exc}"


def _clean_summary_text(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    text = re.sub(r"\s+", " ", text).strip().strip('"').strip("'")
    max_chars = max(30, SCREENER_SUMMARY_MAX_CHARS)
    if len(text) > max_chars:
        text = text[:max_chars].rstrip(" ,.;:") + "..."
    return text


def _parse_summary_response_text(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        parsed = json_mod.loads(text)
        return _clean_summary_text(str(parsed.get("summary", "")))
    except Exception:
        pass

    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            parsed = json_mod.loads(m.group(0))
            return _clean_summary_text(str(parsed.get("summary", "")))
        except Exception:
            pass

    # JSON 파싱 실패 시 텍스트 자체를 한 줄 요약으로 사용
    first_line = text.splitlines()[0] if text else ""
    return _clean_summary_text(first_line)


def _is_generic_summary(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return True
    blocked_patterns = [
        "정보가 제공되지",
        "파악하기 어렵",
        "추가 정보",
        "구체적인 사업 내용을",
        "입력된 정보",
        "확인할 수 없",
        "명시되어 있지",
        "알기 어렵",
        "알 수 없",
    ]
    if any(p in t for p in blocked_patterns):
        return True
    generic_tokens = [
        "투자자",
        "관심",
        "검토",
        "평가",
        "가치",
        "분석",
        "추가 정보",
        "상장된 기업",
        "시장 동향",
    ]
    hit = sum(1 for tok in generic_tokens if tok in t)
    has_business_verb = any(v in t for v in ["제공", "개발", "제조", "운영", "판매", "공급"])
    return hit >= 2 and not has_business_verb


def _template_business_summary(row: dict) -> str:
    company_name = str(row.get("name", "")).strip()
    sector = str(row.get("sector", "N/A")).strip() or "N/A"
    industry = str(row.get("industry", "N/A")).strip() or "N/A"
    label = company_name or str(row.get("symbol", "")).upper().strip() or "해당 기업"

    if industry != "N/A":
        return _clean_summary_text(f"{label}는 {industry} 분야에서 사업을 운영하는 기업입니다.")
    if sector != "N/A":
        return _clean_summary_text(f"{label}는 {sector} 섹터에서 사업을 운영하는 기업입니다.")
    return _clean_summary_text(f"{label}는 특정 산업에서 제품과 서비스를 제공하는 상장 기업입니다.")


def _generate_investor_summary(row: dict, provider: str) -> str:
    provider = (provider or "claude").lower().strip()
    if provider not in ("gemini", "openai", "claude"):
        provider = SCREENER_DEFAULT_PROVIDER

    symbol = str(row.get("symbol", "")).upper().strip()
    company_name = str(row.get("name", "")).strip()
    sector = str(row.get("sector", "N/A")).strip() or "N/A"
    industry = str(row.get("industry", "N/A")).strip() or "N/A"
    if not symbol:
        return ""

    prompt = (
        "다음 입력값을 사용해 해당 회사가 하는 사업을 한국어 한 줄로 설명하세요.\n"
        "공개적으로 알려진 기업 정보를 바탕으로 작성하고, 투자 의견은 쓰지 마세요.\n"
        "입력값:\n"
        f"- symbol: {symbol}\n"
        f"- company_name: {company_name or symbol}\n"
        f"- sector: {sector}\n"
        f"- industry: {industry}\n\n"
        "규칙:\n"
        "1) 한 문장만 작성\n"
        "2) 반드시 '무엇을 제공/개발/제조/운영하는 회사인지'를 포함\n"
        "3) 45~90자 내외\n"
        "4) 다음 표현 금지: 알 수 없음, 확인 불가, 정보 부족, 추가 확인 필요\n"
        "5) 매수/매도/수익 보장/확정적 표현 금지\n"
        "출력은 반드시 JSON만 반환\n"
        "형식: {\"summary\":\"...\"}"
    )
    knowledge_prompt = (
        "티커와 회사명을 바탕으로 해당 기업의 핵심 사업을 한국어 한 문장으로 설명하세요.\n"
        "모르겠다는 표현/불확실 표현(예: 확인 불가, 알 수 없음) 금지.\n"
        "가능한 범위에서 가장 대표적인 사업 영역을 구체적으로 기술하세요.\n"
        "매수/매도 권유 금지.\n"
        "출력은 JSON만 반환.\n"
        f"입력: symbol={symbol}, company_name={company_name or symbol}\n"
        "형식: {\"summary\":\"...\"}"
    )
    tried = set()
    provider_chain = [provider, "gemini", "openai", "claude"]
    def _ask_provider(p: str, user_prompt: str) -> str:
        if p == "gemini":
            if not os.environ.get("GEMINI_API_KEY"):
                return ""
            from google import genai

            client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
            resp = client.models.generate_content(
                model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
                contents=user_prompt,
            )
            return (resp.text or "").strip()
        if p == "openai":
            if not os.environ.get("OPENAI_API_KEY"):
                return ""
            from openai import OpenAI

            client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
            resp = client.chat.completions.create(
                model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
                messages=[
                    {"role": "system", "content": "Return only strict JSON."},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
            )
            return (resp.choices[0].message.content or "").strip()
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return ""
        from anthropic import Anthropic

        client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        resp = client.messages.create(
            model=os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
            max_tokens=140,
            system="Return only strict JSON.",
            messages=[{"role": "user", "content": user_prompt}],
        )
        return "".join(
            block.text for block in resp.content if getattr(block, "type", "") == "text"
        ).strip()

    for p in provider_chain:
        if p in tried:
            continue
        tried.add(p)
        try:
            text = _ask_provider(p, prompt)

            summary = _parse_summary_response_text(text)
            if summary and not _is_generic_summary(summary):
                return summary
        except Exception:
            continue

    # 정보 누락 시 티커/회사명 기반 2차 생성 시도
    for p in provider_chain:
        try:
            text = _ask_provider(p, knowledge_prompt)
            summary = _parse_summary_response_text(text)
            if summary and not _is_generic_summary(summary):
                return summary
        except Exception:
            continue

    return _template_business_summary(row)


def _attach_investor_summaries(rows: list[dict], provider: str) -> list[dict]:
    rows = list(rows or [])
    if not rows:
        return rows

    rows = _enrich_profile_for_summaries(rows)
    workers = max(1, min(SCREENER_SUMMARY_WORKERS, len(rows)))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_generate_investor_summary, row, provider): row for row in rows}
        for f in as_completed(futures):
            row = futures[f]
            try:
                row["summary"] = f.result() or ""
            except Exception:
                row["summary"] = ""
    return rows


def _deep_canslim_snapshot(symbol: str, provider: str) -> dict | None:
    try:
        import yfinance as yf
        from core.data_fetcher import fetch_stock_data, calculate_moving_averages
        from core.pattern_detector import run_pattern_detection
        from canslim import c_current_earnings
        from canslim import a_annual_earnings
        from canslim import s_supply_demand
        from canslim import n_new_catalyst

        stock = yf.Ticker(symbol)
        info = stock.info or {}
        df = fetch_stock_data(symbol, period="3y", interval="1wk")
        df = calculate_moving_averages(df, short_window=10, long_window=40)
        pattern = run_pattern_detection(df, symbol)
        c_data = c_current_earnings.analyze(stock, info)
        a_data = a_annual_earnings.analyze(stock, info)
        s_data = s_supply_demand.analyze(stock, info)
        # 스크리너 배치 성능을 위해 N의 외부 AI 조사 비활성화
        n_data = n_new_catalyst.analyze(stock, info, enable_ai=False)
        chart = pattern or {}
        ai_catalyst = n_data.get("ai_catalyst") or {}

        detail = {
            "symbol": symbol,
            "name": info.get("shortName") or info.get("longName") or symbol,
            "sector": info.get("sector") or "N/A",
            "industry": info.get("industry") or "N/A",
            "chart": {
                "best_pattern": (chart.get("best_pattern") or {}).get("type"),
                "pattern_quality": _safe_float((chart.get("best_pattern") or {}).get("quality_score"), 0.0),
                "pattern_faults": chart.get("pattern_faults", []),
                "rs_rating": _safe_float((chart.get("rs_analysis") or {}).get("rs_rating"), 50.0),
                "rs_trend": (chart.get("rs_analysis") or {}).get("rs_trend"),
                "volume_trend": (chart.get("volume_analysis") or {}).get("recent_volume_trend"),
                "accumulation_weeks": (chart.get("volume_analysis") or {}).get("accumulation_weeks"),
                "distribution_weeks": (chart.get("volume_analysis") or {}).get("distribution_weeks"),
                "base_stage": (chart.get("base_stage") or {}).get("stage"),
            },
            "C": {
                "latest_eps_yoy": (c_data.get("quarterly_eps_growth_yoy") or [None])[0],
                "revenue_growth": c_data.get("revenue_growth"),
                "eps_acceleration": c_data.get("eps_acceleration"),
            },
            "A": {
                "consecutive_growth_years": a_data.get("consecutive_growth_years"),
                "roe": a_data.get("roe"),
                "latest_annual_yoy": (a_data.get("annual_growth_rates") or [None])[0],
            },
            "S": {
                "market_cap": s_data.get("market_cap"),
                "debt_to_equity": s_data.get("debt_to_equity"),
                "buyback_detected": s_data.get("buyback_detected"),
                "insider_pct": s_data.get("insider_pct"),
            },
            "N": {
                "from_high_pct": 100.0 + _safe_float(n_data.get("pct_from_52w_high"), -100.0),
                "near_52w_high": n_data.get("near_52w_high"),
                "has_meaningful_catalyst": ai_catalyst.get("has_meaningful_catalyst"),
                "catalyst_summary": ai_catalyst.get("catalyst_summary"),
            },
        }
        ai_score, ai_reason = _ai_score_candidate(detail, provider=provider)
        detail["ai_score"] = ai_score
        detail["ai_reason"] = ai_reason
        return detail
    except Exception as exc:
        print(f"[WARN] deep snapshot failed for {symbol}: {exc}")
        return None


def _provider_status() -> dict:
    return {
        "gemini": bool(os.environ.get("GEMINI_API_KEY")),
        "openai": bool(os.environ.get("OPENAI_API_KEY")),
        "claude": bool(os.environ.get("ANTHROPIC_API_KEY")),
    }


# ── 헬스체크 ────────────────────────────────────────
@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        modes=["trading", "analysis"],
    )


@app.get("/api/providers/status")
async def providers_status():
    status = _provider_status()
    default_provider = "gemini" if status["gemini"] else (
        "openai" if status["openai"] else ("claude" if status["claude"] else "gemini")
    )
    return {"providers": status, "default": default_provider}


def _compute_screener(req: ScreenerRequest) -> dict:
    class _Deps:
        safe_float = staticmethod(_safe_float)
        get_us_index_universe = staticmethod(_get_us_index_universe)
        get_sp500_symbols = staticmethod(_get_sp500_symbols)
        collect_snapshots_throttled = staticmethod(_collect_snapshots_throttled)
        percentile_rank = staticmethod(_percentile_rank)
        dedupe_rows = staticmethod(_dedupe_rows)
        sort_rows = staticmethod(_sort_screener_rows)
        deep_canslim_snapshot = staticmethod(_deep_canslim_snapshot)
        enrich_result_metrics = staticmethod(_enrich_result_metrics)
        attach_summaries = staticmethod(_attach_investor_summaries)

    return screener_compute(
        req,
        _Deps(),
        default_provider=SCREENER_DEFAULT_PROVIDER,
        phase1_workers=SCREENER_PHASE1_WORKERS,
        phase2_workers=SCREENER_PHASE2_WORKERS,
        batch_size=SCREENER_BATCH_SIZE,
        batch_pause_sec=SCREENER_BATCH_PAUSE_SEC,
    )


screener_service = ScreenerService(
    load_cache=_load_screener_cache,
    save_cache=_save_screener_cache,
    refresh_state_snapshot=_refresh_state_snapshot,
    start_refresh=_start_screener_refresh,
    build_refresh_scan_request=_build_refresh_scan_request,
    bootstrap_cache_fast=_bootstrap_screener_cache_fast,
    sort_rows=_sort_screener_rows,
    dedupe_rows=_dedupe_rows,
    is_default_cache_request=_is_default_cache_request,
    attach_summaries=_attach_investor_summaries,
    start_summary_backfill=_start_cache_summary_backfill,
    compute_screener=_compute_screener,
    default_provider=SCREENER_DEFAULT_PROVIDER,
    refresh_policy=SCREENER_REFRESH_POLICY,
)

app.include_router(create_screener_router(screener_service))


# ── 종목 검색 API ─────────────────────────────────
@app.get("/api/search")
async def search_stocks(q: str = ""):
    """종목명/티커로 검색 (Yahoo Finance autosuggest 프록시)"""
    query = q.strip()
    if not query or len(query) < 1:
        return {"results": []}

    import urllib.request
    import urllib.parse
    import json as json_mod

    try:
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={urllib.parse.quote(query)}&quotesCount=8&newsCount=0&enableFuzzyQuery=true&quotesQueryId=tss_match_phrase_query"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json_mod.loads(resp.read().decode())

        results = []
        for item in data.get("quotes", []):
            symbol = item.get("symbol", "")
            name = item.get("shortname") or item.get("longname") or ""
            exchange = item.get("exchange", "")
            qtype = item.get("quoteType", "")
            if qtype in ("EQUITY", "ETF"):
                results.append({
                    "symbol": symbol,
                    "name": name,
                    "exchange": exchange,
                    "type": qtype,
                })
        return {"results": results}

    except Exception as e:
        print(f"[WARN] Search API error: {e}")
        return {"results": []}


# ── 트레이딩 모드 API ───────────────────────────────
@app.post("/api/trading/analyze", response_model=TradingResponse)
async def trading_analyze(request: TradingRequest):
    """트레이딩 모드 — 차트 + 패턴 + CAN SLIM"""
    ticker = request.ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker는 필수 항목입니다.")

    mode = request.mode
    if mode not in ("v1", "v2"):
        raise HTTPException(status_code=400, detail="mode는 'v1' 또는 'v2'만 가능합니다.")

    interval = request.interval
    if interval not in ("1wk", "1d"):
        raise HTTPException(status_code=400, detail="interval은 '1wk' 또는 '1d'만 가능합니다.")

    provider = request.provider.strip().lower()
    if provider not in ("gemini", "openai", "claude"):
        raise HTTPException(status_code=400, detail="provider는 gemini/openai/claude만 가능합니다.")

    if provider == "gemini" and not os.environ.get("GEMINI_API_KEY"):
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY가 설정되지 않았습니다.")
    if provider == "openai" and not os.environ.get("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY가 설정되지 않았습니다.")
    if provider == "claude" and not os.environ.get("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY가 설정되지 않았습니다.")

    original_cwd = os.getcwd()
    os.chdir(str(TRADING_DIR))

    try:
        from core.data_fetcher import fetch_stock_data, calculate_moving_averages
        from core.chart_generator import create_oneil_chart
        from core.ai_analyzer import analyze_chart_with_gemini, analyze_chart_v2, parse_pattern_data
        from core.pattern_detector import run_pattern_detection
        from core.fundamental_analyzer import analyze_fundamentals
        from core.feedback_manager import FeedbackManager

        if interval == "1wk":
            short_window, long_window, period = 10, 40, "3y"
        else:
            short_window, long_window, period = 50, 200, "1y"

        df = fetch_stock_data(ticker, period=period, interval=interval)
        df = calculate_moving_averages(df, short_window=short_window, long_window=long_window)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            chart_path = tmp.name

        create_oneil_chart(ticker, df, output_path=chart_path, interval=interval)

        analysis = ""
        pattern_data = None
        feedback_manager = FeedbackManager()

        if mode == "v1":
            analysis = analyze_chart_with_gemini(
                chart_path,
                ticker,
                df,
                feedback_manager,
                interval=interval,
                provider=provider,
            )
            parsed = parse_pattern_data(analysis)
            if parsed:
                pattern_data = parsed
        else:
            pattern_result = run_pattern_detection(df, ticker)
            fundamental_result = analyze_fundamentals(
                ticker, rs_analysis=pattern_result.get("rs_analysis")
            )
            analysis = analyze_chart_v2(
                chart_path,
                ticker,
                df,
                pattern_result,
                feedback_manager,
                fundamental_result=fundamental_result,
                interval=interval,
                provider=provider,
            )
            pattern_data = {
                "best_pattern": pattern_result.get("best_pattern"),
                "base_stage": pattern_result.get("base_stage"),
                "volume_analysis": {
                    "accumulation_weeks": pattern_result["volume_analysis"].get("accumulation_weeks"),
                    "distribution_weeks": pattern_result["volume_analysis"].get("distribution_weeks"),
                    "recent_volume_trend": pattern_result["volume_analysis"].get("recent_volume_trend"),
                },
                "rs_analysis": {
                    "rs_rating": pattern_result.get("rs_analysis", {}).get("rs_rating"),
                    "rs_trend": pattern_result.get("rs_analysis", {}).get("rs_trend"),
                    "rs_new_high": pattern_result.get("rs_analysis", {}).get("rs_new_high"),
                },
                "pattern_faults": pattern_result.get("pattern_faults", []),
            }

        chart_base64 = None
        if os.path.exists(chart_path):
            with open(chart_path, "rb") as f:
                chart_base64 = f"data:image/png;base64,{base64.b64encode(f.read()).decode()}"
            os.unlink(chart_path)

        if pattern_data:
            pattern_data = convert_numpy(pattern_data)

        return TradingResponse(
            ticker=ticker,
            mode=mode,
            analysis=analysis,
            pattern_data=pattern_data,
            chart_base64=chart_base64,
            timestamp=datetime.now().isoformat(),
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"트레이딩 분석 오류: {str(e)}")
    finally:
        os.chdir(original_cwd)


# ── 분석 모드 API ────────────────────────────────────
@app.post("/api/analysis/analyze", response_model=AnalysisResponse)
async def analysis_analyze(request: AnalysisRequest):
    """분석 모드 — 순수 CAN SLIM 펀더멘털"""
    ticker = request.ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker는 필수 항목입니다.")

    provider = request.provider.strip().lower()
    if provider not in ("gemini", "openai", "claude"):
        raise HTTPException(status_code=400, detail="provider는 gemini/openai/claude만 가능합니다.")
    if provider == "gemini" and not os.environ.get("GEMINI_API_KEY"):
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY가 설정되지 않았습니다.")
    if provider == "openai" and not os.environ.get("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY가 설정되지 않았습니다.")
    if provider == "claude" and not os.environ.get("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY가 설정되지 않았습니다.")

    original_cwd = os.getcwd()
    os.chdir(str(PROJECT_ROOT))

    try:
        from src.analyzer import run_analysis
        from src.ai_client import analyze_fundamentals_with_ai

        fundamental_result = run_analysis(ticker)

        if fundamental_result.get('error'):
            raise HTTPException(status_code=400, detail=fundamental_result['error'])

        ai_analysis = analyze_fundamentals_with_ai(
            ticker,
            fundamental_result['prompt_text'],
            provider=provider,
        )

        data = fundamental_result.get('data', {})
        currency = fundamental_result.get('currency', 'USD')
        summary = _build_summary(data, currency)
        safe_data = convert_numpy(data)

        return AnalysisResponse(
            ticker=ticker,
            company_name=fundamental_result.get('company_name', ''),
            currency=currency,
            summary=summary,
            ai_analysis=ai_analysis,
            fundamental_data=safe_data,
            timestamp=datetime.now().isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"분석 모드 오류: {str(e)}")
    finally:
        os.chdir(original_cwd)


def _build_summary(data: dict, currency: str) -> dict:
    """프론트엔드용 CAN SLIM 요약 데이터"""
    summary = {}

    c = data.get('C', {})
    eps_growth_list = c.get('quarterly_eps_growth_yoy', [])
    quarterly_ni = c.get('quarterly_net_income', [])
    summary['C'] = {
        'eps_yoy': eps_growth_list[0] if eps_growth_list and eps_growth_list[0] is not None else None,
        'eps_growth_trend': eps_growth_list[:4] if eps_growth_list else [],
        'revenue_yoy': c.get('revenue_growth'),
        'acceleration': c.get('eps_acceleration', ''),
        'quarter': quarterly_ni[0].get('period', '') if quarterly_ni else '',
    }

    a = data.get('A', {})
    annual_ni = a.get('annual_net_income', [])
    annual_rates = a.get('annual_growth_rates', [])
    summary['A'] = {
        'latest_year': annual_ni[0].get('year', '') if annual_ni else '',
        'eps_yoy': annual_rates[0] if annual_rates and annual_rates[0] is not None else None,
        'growth_rates': annual_rates[:4] if annual_rates else [],
        'consecutive_years': a.get('consecutive_growth_years', 0),
        'roe': a.get('roe'),
        'pe_ratio': a.get('pe_ratio'),
        'profit_margins': a.get('profit_margins'),
    }

    n = data.get('N', {})
    summary['N'] = {
        'catalyst_count': len(n.get('catalysts', [])),
        'near_52w_high': n.get('near_52w_high', False),
    }

    s = data.get('S', {})
    summary['S'] = {
        'market_cap': s.get('market_cap'),
        'market_cap_label': s.get('market_cap_label', ''),
        'debt_to_equity': s.get('debt_to_equity'),
        'buyback': s.get('buyback_detected', False),
    }

    l_data = data.get('L', {})
    summary['L'] = {
        'rs_rating': l_data.get('rs_rating'),
        'rs_trend': l_data.get('rs_trend', 'N/A'),
        'benchmark': l_data.get('benchmark', ''),
    }

    i = data.get('I', {})
    summary['I'] = {
        'inst_pct': i.get('inst_holders_pct'),
        'inst_count': i.get('inst_holders_count'),
    }

    m = data.get('M', {})
    m_summary = {}
    for key in ['sp500', 'nasdaq', 'kospi', 'kosdaq']:
        idx = m.get(key, {})
        if idx and idx.get('current_price'):
            m_summary[key] = {
                'trend': idx.get('trend', 'N/A'),
                'distribution_days': idx.get('distribution_days_5wk', 0),
            }
    summary['M'] = m_summary

    return summary


# ── 커뮤니티 투표 시스템 (서버 메모리 기반) ───────────
_polls_lock = threading.Lock()
_polls_data: dict = {}       # { "AAPL": {"bullish": 0, "neutral": 0, "bearish": 0} }
_user_votes: dict = {}       # { "session_id:ticker": "bullish" }

POLLS_FILE = PROJECT_ROOT / "polls_data.json"

def _load_polls():
    global _polls_data, _user_votes
    if POLLS_FILE.exists():
        try:
            with open(POLLS_FILE, "r") as f:
                saved = json_mod.load(f)
                _polls_data = saved.get("polls", {})
                _user_votes = saved.get("votes", {})
        except Exception:
            pass

def _save_polls():
    try:
        with open(POLLS_FILE, "w") as f:
            json_mod.dump({"polls": _polls_data, "votes": _user_votes}, f)
    except Exception:
        pass

_load_polls()


class VoteRequest(BaseModel):
    ticker: str
    vote_type: str = Field(..., description="bullish, neutral, bearish")
    session_id: str = Field(default="anonymous", description="브라우저 세션 ID")


@app.get("/api/community/polls")
async def get_polls():
    """모든 투표 현황 조회"""
    with _polls_lock:
        return {"polls": _polls_data}


@app.post("/api/community/vote")
async def cast_vote(req: VoteRequest):
    """투표 등록/변경/취소"""
    ticker = req.ticker.strip().upper()
    vote_type = req.vote_type.strip().lower()
    if vote_type not in ("bullish", "neutral", "bearish"):
        raise HTTPException(status_code=400, detail="vote_type must be bullish, neutral, or bearish")

    vote_key = f"{req.session_id}:{ticker}"

    with _polls_lock:
        if ticker not in _polls_data:
            _polls_data[ticker] = {"bullish": 0, "neutral": 0, "bearish": 0}

        poll = _polls_data[ticker]
        prev_vote = _user_votes.get(vote_key)

        # 이전 투표가 있으면 제거
        if prev_vote and prev_vote in poll:
            poll[prev_vote] = max(0, poll[prev_vote] - 1)

        if prev_vote == vote_type:
            # 같은 버튼 다시 누르면 취소
            del _user_votes[vote_key]
        else:
            poll[vote_type] = poll.get(vote_type, 0) + 1
            _user_votes[vote_key] = vote_type

        _save_polls()
        return {"polls": _polls_data, "user_vote": _user_votes.get(vote_key)}


@app.post("/api/community/add_ticker")
async def add_community_ticker(req: dict):
    """분석 완료된 종목을 커뮤니티에 자동 등록"""
    ticker = req.get("ticker", "").strip().upper()
    name = req.get("name", "")
    analyst = req.get("analyst", "윌리엄 오닐 AI")
    verdict = req.get("verdict", "")
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker required")

    with _polls_lock:
        if ticker not in _polls_data:
            _polls_data[ticker] = {
                "bullish": 0, "neutral": 0, "bearish": 0,
                "name": name, "analyst": analyst, "verdict": verdict,
                "date": datetime.now().strftime("%Y-%m-%d"),
            }
            _save_polls()
    return {"ok": True}


@app.post("/api/community/seed")
async def seed_community(req: dict):
    """초기 시드 데이터 등록 (이미 있으면 무시)"""
    items = req.get("items", [])
    with _polls_lock:
        for item in items:
            ticker = item.get("ticker", "").strip().upper()
            if ticker and ticker not in _polls_data:
                _polls_data[ticker] = {
                    "bullish": item.get("bullish", 0),
                    "neutral": item.get("neutral", 0),
                    "bearish": item.get("bearish", 0),
                    "name": item.get("name", ""),
                    "analyst": item.get("analyst", ""),
                    "verdict": item.get("verdict", ""),
                    "date": item.get("date", ""),
                }
        _save_polls()
    return {"ok": True, "total": len(_polls_data)}


@app.get("/api/community/user_votes")
async def get_user_votes(session_id: str = "anonymous"):
    """특정 세션의 투표 내역 조회"""
    prefix = f"{session_id}:"
    votes = {}
    with _polls_lock:
        for key, val in _user_votes.items():
            if key.startswith(prefix):
                ticker = key[len(prefix):]
                votes[ticker] = val
    return {"votes": votes}


# ── 정적 파일 서빙 (프론트엔드) ─────────────────────
_frontend_candidates = [
    REPO_ROOT / "frontend" / "integrated_ui",  # monorepo root layout
    PROJECT_ROOT / "frontend",                 # bundled-in-service layout
]
FRONTEND_DIR = next((p for p in _frontend_candidates if p.exists()), None)
if FRONTEND_DIR:
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
