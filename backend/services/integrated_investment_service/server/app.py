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


class ScreenerRequest(BaseModel):
    market: str = Field(default="US", description="현재 US만 지원")
    min_market_cap: float = Field(default=500_000_000, description="최소 시가총액(USD)")
    sort_by: str = Field(default="score", description="정렬: score/rs/eps_growth/revenue_growth/from_high")
    max_results: int = Field(default=100, description="반환 결과 수")
    provider: str = Field(default="claude", description="AI 제공자: gemini/openai/claude")
    prefilter_count: int = Field(default=160, description="1차 후보 선별 수")
    ai_rerank_count: int = Field(default=100, description="AI 0~99 점수 재평가할 종목 수")
    use_cache: bool = Field(default=True, description="캐시 사용 여부")
    force_refresh: bool = Field(default=False, description="캐시 무시 후 재계산")


class ScreenerRefreshRequest(BaseModel):
    secret: Optional[str] = Field(default=None, description="갱신 보호 토큰")
    provider: str = Field(default="claude", description="AI 제공자")
    min_market_cap: float = Field(default=500_000_000, description="최소 시가총액(USD)")
    max_results: int = Field(default=100, description="반환 결과 수")


SCREENER_CACHE_FILE = PROJECT_ROOT / "screener_cache.json"
SCREENER_CACHE_LOCK = threading.Lock()
SCREENER_DEFAULT_MARKET = "US"
SCREENER_DEFAULT_MIN_MARKET_CAP = 500_000_000.0
SCREENER_DEFAULT_PROVIDER = "claude"
SCREENER_REFRESH_POLICY = "매주 월요일 오전 9시(KST) 갱신"
SCREENER_PHASE1_WORKERS = int(os.environ.get("SCREENER_PHASE1_WORKERS", "4"))
SCREENER_PHASE2_WORKERS = int(os.environ.get("SCREENER_PHASE2_WORKERS", "1"))
SCREENER_BATCH_SIZE = int(os.environ.get("SCREENER_BATCH_SIZE", "80"))
SCREENER_BATCH_PAUSE_SEC = float(os.environ.get("SCREENER_BATCH_PAUSE_SEC", "0.5"))


def _load_screener_cache() -> Optional[dict]:
    with SCREENER_CACHE_LOCK:
        if not SCREENER_CACHE_FILE.exists():
            return None
        try:
            with open(SCREENER_CACHE_FILE, "r") as f:
                return json_mod.load(f)
        except Exception:
            return None


def _save_screener_cache(payload: dict):
    with SCREENER_CACHE_LOCK:
        with open(SCREENER_CACHE_FILE, "w") as f:
            json_mod.dump(payload, f, ensure_ascii=False)


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
    import urllib.request
    import urllib.parse

    try:
        sym = urllib.parse.quote(symbol)
        url = (
            f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{sym}"
            "?modules=financialData,price"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json_mod.loads(resp.read().decode())
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


def _enrich_result_metrics(rows: list[dict]) -> list[dict]:
    import urllib.request
    import urllib.parse

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
                data = json_mod.loads(resp.read().decode())
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

    # 2) EPS/매출 성장 보강 (값이 비어있는 종목만)
    targets = [
        r for r in rows
        if _safe_float(r.get("eps_growth"), 0.0) == 0.0
        and _safe_float(r.get("revenue_growth"), 0.0) == 0.0
    ]
    if targets:
        with ThreadPoolExecutor(max_workers=6) as ex:
            futures = {
                ex.submit(_fetch_yahoo_growth_snapshot, str(r.get("symbol", "")).upper()): r
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
    provider = (req.provider or SCREENER_DEFAULT_PROVIDER).strip().lower()
    if provider not in ("gemini", "openai", "claude"):
        provider = SCREENER_DEFAULT_PROVIDER

    try:
        import yfinance as yf
    except Exception:
        raise HTTPException(status_code=500, detail="yfinance 의존성이 설치되지 않았습니다.")

    symbols = sorted(_get_us_index_universe())
    sp500_symbols = _get_sp500_symbols()
    if not symbols:
        raise HTTPException(status_code=500, detail="스크리너 유니버스를 구성하지 못했습니다.")

    benchmark_hist = yf.Ticker("^GSPC").history(period="1y", interval="1d", auto_adjust=False)
    if benchmark_hist is None or benchmark_hist.empty:
        raise HTTPException(status_code=500, detail="벤치마크 데이터를 불러오지 못했습니다.")
    bclose = benchmark_hist["Close"].dropna()
    if len(bclose) < 120:
        raise HTTPException(status_code=500, detail="벤치마크 데이터가 충분하지 않습니다.")
    b_now = _safe_float(bclose.iloc[-1], 0.0)
    b_6m = _safe_float(bclose.iloc[max(0, len(bclose) - 126)], 0.0)
    b_12m = _safe_float(bclose.iloc[0], 0.0)
    bench_6m = ((b_now / b_6m) - 1.0) if b_6m > 0 else 0.0
    bench_12m = ((b_now / b_12m) - 1.0) if b_12m > 0 else 0.0

    phase1_map = _collect_snapshots_throttled(
        symbols=symbols,
        bench_6m=bench_6m,
        bench_12m=bench_12m,
        include_info=False,
        workers=SCREENER_PHASE1_WORKERS,
        batch_size=SCREENER_BATCH_SIZE,
        pause_sec=SCREENER_BATCH_PAUSE_SEC,
    )
    snapshots = list(phase1_map.values())

    if not snapshots:
        raise HTTPException(status_code=500, detail="종목 데이터를 불러오지 못했습니다.")

    rs_values = [s["rs_raw"] for s in snapshots]
    ranked = []
    for s in snapshots:
        rs_score = _percentile_rank(rs_values, s["rs_raw"])
        s["rs_score"] = round(rs_score, 1)

        fh = max(0.0, min(100.0, s["from_high_pct"]))
        eps_n = max(0.0, min(100.0, 50.0 + s["eps_growth"] * 1.2))
        rev_n = max(0.0, min(100.0, 50.0 + s["revenue_growth"] * 1.0))
        vol_n = max(0.0, min(100.0, s["vol_ratio"] * 40.0))
        score = fh * 0.35 + rs_score * 0.35 + eps_n * 0.20 + rev_n * 0.05 + vol_n * 0.05
        s["score"] = round(score, 1)

        ranked.append(s)

    ranked, _ = _dedupe_rows(ranked)
    ranked = _sort_screener_rows(ranked, "score")

    # 대유니버스에서는 상위 후보만 info 조회 후 시총 필터 적용
    candidate_n = max(prefilter_count, max_results * 2, ai_rerank_count * 2)
    candidates = ranked[:min(candidate_n, len(ranked))]
    enriched_map = _collect_snapshots_throttled(
        symbols=[row["symbol"] for row in candidates],
        bench_6m=bench_6m,
        bench_12m=bench_12m,
        include_info=True,
        workers=SCREENER_PHASE2_WORKERS,
        batch_size=max(20, SCREENER_BATCH_SIZE // 2),
        pause_sec=max(0.8, SCREENER_BATCH_PAUSE_SEC),
    )

    filtered = []
    for row in candidates:
        symbol = row["symbol"]
        info_row = enriched_map.get(symbol)
        if info_row:
            row["name"] = info_row.get("name", row.get("name", symbol))
            row["sector"] = info_row.get("sector", row.get("sector", "N/A"))
            row["market_cap"] = info_row.get("market_cap", row.get("market_cap", 0))
            row["eps_growth"] = info_row.get("eps_growth", row.get("eps_growth", 0))
            row["revenue_growth"] = info_row.get("revenue_growth", row.get("revenue_growth", 0))
        mcap = _safe_float(row.get("market_cap"), 0.0)
        is_sp500 = symbol in sp500_symbols
        if mcap < min_market_cap and not is_sp500:
            continue
        filtered.append(row)

    filtered, _ = _dedupe_rows(filtered)
    filtered = _sort_screener_rows(filtered, "score")
    preselected = filtered[:prefilter_count]

    deep_n = min(len(preselected), max(max_results, ai_rerank_count))
    deep_targets = preselected[:deep_n]
    deep_map = {}
    if deep_targets:
        with ThreadPoolExecutor(max_workers=min(4, deep_n)) as ex:
            futures = {
                ex.submit(_deep_canslim_snapshot, row["symbol"], provider): row["symbol"]
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
            row["deep"] = deep
            chart = deep.get("chart", {})
            row["chart_pattern"] = chart.get("best_pattern")
            row["pattern_quality"] = chart.get("pattern_quality")
            row["canslim_rs_rating"] = chart.get("rs_rating")
        else:
            row["ai_score"] = int(row.get("score", 0))
            row["ai_reason"] = "AI 재평가 미적용(정량 점수 사용)"

    preselected = _sort_screener_rows(preselected, sort_by)
    preselected, dup_removed = _dedupe_rows(preselected)
    results = preselected[:max_results]
    results = _enrich_result_metrics(results)
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


@app.get("/api/screener/cache/status")
async def screener_cache_status():
    cache = _load_screener_cache()
    if not cache:
        return {"ready": False, "refresh_policy": SCREENER_REFRESH_POLICY}
    return {
        "ready": True,
        "analyzed_at": cache.get("analyzed_at"),
        "result_count": len(cache.get("results", [])),
        "provider": cache.get("provider", SCREENER_DEFAULT_PROVIDER),
        "refresh_policy": SCREENER_REFRESH_POLICY,
    }


@app.post("/api/screener/refresh")
async def screener_refresh(req: ScreenerRefreshRequest):
    token = os.environ.get("SCREENER_REFRESH_TOKEN")
    if token and req.secret != token:
        raise HTTPException(status_code=403, detail="refresh token mismatch")

    scan_req = ScreenerRequest(
        market="US",
        min_market_cap=req.min_market_cap,
        sort_by="score",
        max_results=req.max_results,
        provider=req.provider,
        prefilter_count=max(160, req.max_results + 60),
        ai_rerank_count=min(20, req.max_results),
        use_cache=False,
        force_refresh=True,
    )
    data = _compute_screener(scan_req)
    _save_screener_cache(data)
    data["cache_hit"] = False
    data["refresh_policy"] = SCREENER_REFRESH_POLICY
    return data


@app.post("/api/screener/scan")
async def screener_scan(req: ScreenerRequest):
    """CAN SLIM 스크리너 (기본 요청은 캐시 우선)."""
    sort_by = (req.sort_by or "score").lower()
    max_results = max(1, min(int(req.max_results), 100))
    cache = _load_screener_cache()
    use_cache = bool(req.use_cache) and not bool(req.force_refresh)
    default_cache_req = _is_default_cache_request(req)

    if use_cache and cache and default_cache_req:
        cached_rows = _sort_screener_rows(cache.get("results", []), sort_by)
        cached_rows, dup_removed = _dedupe_rows(cached_rows)
        return {
            **{k: v for k, v in cache.items() if k != "results"},
            "results": cached_rows[:max_results],
            "duplicates_removed": dup_removed,
            "cache_hit": True,
            "refresh_policy": SCREENER_REFRESH_POLICY,
            "timestamp": datetime.utcnow().isoformat(),
        }

    data = _compute_screener(req)
    data["cache_hit"] = False
    data["refresh_policy"] = SCREENER_REFRESH_POLICY

    if default_cache_req:
        _save_screener_cache(data)

    return data


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
