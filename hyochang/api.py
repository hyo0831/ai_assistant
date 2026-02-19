"""
윌리엄 오닐 AI 투자 어시스턴트 — 로컬 FastAPI 서버
hyochang/core/ 모듈을 직접 사용 (최신 한국어 강제 버전)
"""

import os
import base64
import tempfile
import numpy as np
from datetime import datetime
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from core.version import VERSION, VERSION_NAME


def convert_numpy(obj):
    if isinstance(obj, dict):
        return {k: convert_numpy(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy(i) for i in obj]
    elif isinstance(obj, (np.bool_,)):
        return bool(obj)
    elif isinstance(obj, (np.integer,)):
        return int(obj)
    elif isinstance(obj, (np.floating,)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


@asynccontextmanager
async def lifespan(app: FastAPI):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[WARNING] GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")
    else:
        print(f"[OK] GEMINI_API_KEY 확인됨 (길이: {len(api_key)})")
    print(f"[OK] 로컬 서버 시작 — v{VERSION} ({VERSION_NAME})")
    yield
    print("[OK] 서버 종료")


app = FastAPI(
    title="William O'Neil AI Investment Assistant (Local)",
    description="CAN SLIM 방법론 기반 주식 차트 분석 API",
    version=VERSION,
    lifespan=lifespan,
)

# R3: CORS 오리진 설정 — 환경변수 CORS_ALLOWED_ORIGINS로 재정의 가능
# 예) CORS_ALLOWED_ORIGINS="https://yourdomain.com,https://app.yourdomain.com"
_cors_env = os.environ.get("CORS_ALLOWED_ORIGINS", "")
CORS_ORIGINS = (
    [o.strip() for o in _cors_env.split(",") if o.strip()]
    if _cors_env
    else [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080",
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


class AnalyzeRequest(BaseModel):
    ticker: str = Field(..., description="종목 코드 (예: AAPL, 005930.KS)", examples=["AAPL"])
    mode: str = Field(default="v2", description="분석 모드: v1 또는 v2")
    interval: str = Field(default="1wk", description="차트 간격: 1wk 또는 1d")


class AnalyzeResponse(BaseModel):
    ticker: str
    mode: str
    analysis: str
    pattern_data: dict | None = None
    chart_base64: str | None = None
    timestamp: str


class HealthResponse(BaseModel):
    status: str
    version: str
    version_name: str


@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="healthy", version=VERSION, version_name=VERSION_NAME)


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_stock(request: AnalyzeRequest):
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
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")

    from core.data_fetcher import fetch_stock_data, calculate_moving_averages
    from core.chart_generator import create_oneil_chart
    from core.ai_analyzer import analyze_chart_with_gemini, analyze_chart_v2, parse_pattern_data
    from core.pattern_detector import run_pattern_detection
    from core.feedback_manager import FeedbackManager

    if interval == "1wk":
        short_window, long_window, period = 10, 40, "3y"
    else:
        short_window, long_window, period = 50, 200, "1y"

    try:
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

        return AnalyzeResponse(
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
        raise HTTPException(status_code=500, detail=f"분석 중 오류 발생: {str(e)}")
