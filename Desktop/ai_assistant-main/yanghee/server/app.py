"""
O'Neil AI 투자 어시스턴트 — 통합 FastAPI 서버
트레이딩 모드(trading/) + 분석 모드(src/)를 하나의 API로 제공
배포 루트: yanghee/
"""

import os
import sys
import base64
import tempfile
from datetime import datetime
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Optional
from dotenv import load_dotenv
import threading
import json as json_mod

# 프로젝트 루트 = yanghee/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
TRADING_DIR = PROJECT_ROOT / "trading"

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


class TradingResponse(BaseModel):
    ticker: str
    mode: str
    analysis: str
    pattern_data: dict | None = None
    chart_base64: str | None = None
    timestamp: str


class AnalysisRequest(BaseModel):
    ticker: str = Field(..., description="종목 코드", examples=["AAPL", "005930.KS"])


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


# ── 헬스체크 ────────────────────────────────────────
@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        modes=["trading", "analysis"],
    )


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

    if not os.environ.get("GEMINI_API_KEY"):
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY가 설정되지 않았습니다.")

    original_cwd = os.getcwd()
    os.chdir(str(TRADING_DIR))

    try:
        from core.data_fetcher import fetch_stock_data, calculate_moving_averages
        from core.chart_generator import create_oneil_chart
        from core.ai_analyzer import analyze_chart_with_gemini, analyze_chart_v2, parse_pattern_data
        from core.pattern_detector import run_pattern_detection
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
            analysis = analyze_chart_with_gemini(chart_path, ticker, df, feedback_manager, interval=interval)
            parsed = parse_pattern_data(analysis)
            if parsed:
                pattern_data = parsed
        else:
            pattern_result = run_pattern_detection(df, ticker)
            analysis = analyze_chart_v2(
                chart_path, ticker, df, pattern_result, feedback_manager, interval=interval
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

    if not os.environ.get("GEMINI_API_KEY"):
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY가 설정되지 않았습니다.")

    original_cwd = os.getcwd()
    os.chdir(str(PROJECT_ROOT))

    try:
        from src.analyzer import run_analysis
        from src.ai_client import analyze_fundamentals_with_gemini

        fundamental_result = run_analysis(ticker)

        if fundamental_result.get('error'):
            raise HTTPException(status_code=400, detail=fundamental_result['error'])

        ai_analysis = analyze_fundamentals_with_gemini(ticker, fundamental_result['prompt_text'])

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
FRONTEND_DIR = PROJECT_ROOT / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
