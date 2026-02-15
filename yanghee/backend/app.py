"""
윌리엄 오닐 AI 투자 어시스턴트 — FastAPI 서버
기존 CLI(main.py) 로직을 REST API로 래핑
"""

import os
import base64
import re
import tempfile
import numpy as np
from datetime import datetime
from contextlib import asynccontextmanager


def convert_numpy(obj):
    """numpy 타입을 Python 기본 타입으로 변환 (JSON 직렬화용)"""
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

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from version import VERSION, VERSION_NAME


# ====================================================================
# Lifespan: 서버 시작 시 GEMINI_API_KEY 검증
# ====================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 시작/종료 시 실행되는 로직"""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[WARNING] GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")
        print("  export GEMINI_API_KEY='your-key-here'")
    else:
        print(f"[OK] GEMINI_API_KEY 확인됨 (길이: {len(api_key)})")
    print(f"[OK] 서버 시작 — v{VERSION} ({VERSION_NAME})")
    yield
    print("[OK] 서버 종료")


# ====================================================================
# FastAPI 앱 생성
# ====================================================================

app = FastAPI(
    title="William O'Neil AI Investment Assistant",
    description="CAN SLIM 방법론 기반 주식 차트 분석 API",
    version=VERSION,
    lifespan=lifespan,
)

# CORS 설정 — 프론트엔드에서 이 API를 호출할 수 있도록 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 프론트엔드 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 모든 에러에 CORS 헤더를 포함시키는 핸들러
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": f"서버 내부 오류: {str(exc)}"},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        },
    )


# ====================================================================
# Request / Response 모델 정의
# ====================================================================

class AnalyzeRequest(BaseModel):
    """분석 요청 Body"""
    ticker: str = Field(..., description="종목 코드 (예: AAPL, 005930.KS)", examples=["AAPL"])
    mode: str = Field(default="v2", description="분석 모드: v1(기본 AI) 또는 v2(패턴감지+AI)")
    interval: str = Field(default="1wk", description="차트 간격: 1wk(주봉) 또는 1d(일봉)")


class AnalyzeResponse(BaseModel):
    """분석 응답"""
    ticker: str
    mode: str
    analysis: str
    pattern_data: dict | None = None
    chart_base64: str | None = None
    timestamp: str


class HealthResponse(BaseModel):
    """헬스체크 응답"""
    status: str
    version: str
    version_name: str


# ====================================================================
# 엔드포인트
# ====================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """서버 상태 확인 (GCP 헬스체크용)"""
    return HealthResponse(
        status="healthy",
        version=VERSION,
        version_name=VERSION_NAME,
    )


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_stock(request: AnalyzeRequest):
    """
    주식 차트 분석 API

    1. ticker로 주가 데이터 다운로드 (yfinance)
    2. 이동평균선 계산
    3. 차트 생성
    4. AI 분석 실행 (Gemini)
    5. JSON 응답 반환
    """

    # --- 입력 검증 ---
    ticker = request.ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker는 필수 항목입니다.")

    mode = request.mode
    if mode not in ("v1", "v2"):
        raise HTTPException(status_code=400, detail="mode는 'v1' 또는 'v2'만 가능합니다.")

    interval = request.interval
    if interval not in ("1wk", "1d"):
        raise HTTPException(status_code=400, detail="interval은 '1wk' 또는 '1d'만 가능합니다.")

    # --- GEMINI_API_KEY 확인 ---
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="GEMINI_API_KEY 환경변수가 설정되지 않았습니다."
        )

    # --- 지연 import (서버 시작 속도 최적화) ---
    from main import (
        fetch_stock_data,
        calculate_moving_averages,
        create_oneil_chart,
        analyze_chart_with_gemini,
        parse_pattern_data,
    )
    from pattern_detector import run_pattern_detection
    from feedback_manager import FeedbackManager

    # --- 이동평균 기간 설정 ---
    if interval == "1wk":
        short_window, long_window = 10, 40
        period = "3y"
    else:
        short_window, long_window = 50, 200
        period = "1y"

    try:
        # Step 1: 데이터 다운로드
        df = fetch_stock_data(ticker, period=period, interval=interval)

        # Step 2: 이동평균선 계산
        df = calculate_moving_averages(df, short_window=short_window, long_window=long_window)

        # Step 3: 임시 파일에 차트 생성
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            chart_path = tmp.name

        create_oneil_chart(ticker, df, output_path=chart_path, interval=interval)

        # Step 4: 분석 실행
        analysis = ""
        pattern_data = None

        if mode == "v1":
            feedback_manager = FeedbackManager()
            analysis = analyze_chart_with_gemini(chart_path, ticker, df, feedback_manager)
            pattern_data_parsed = parse_pattern_data(analysis)
            if pattern_data_parsed:
                pattern_data = pattern_data_parsed

        else:  # v2
            pattern_result = run_pattern_detection(df, ticker)

            from main import analyze_chart_v2
            feedback_manager = FeedbackManager()
            analysis = analyze_chart_v2(
                chart_path, ticker, df, pattern_result, feedback_manager
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

        # Step 5: 차트 이미지를 Base64로 인코딩
        chart_base64 = None
        if os.path.exists(chart_path):
            with open(chart_path, "rb") as f:
                chart_bytes = f.read()
            chart_base64 = f"data:image/png;base64,{base64.b64encode(chart_bytes).decode()}"
            os.unlink(chart_path)  # 임시 파일 삭제

        # numpy 타입을 Python 기본 타입으로 변환
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
