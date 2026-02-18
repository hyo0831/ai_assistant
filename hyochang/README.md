# 윌리엄 오닐 AI 투자 어시스턴트 (William O'Neil AI Investment Assistant)

> **Version 2.1.0** | Google Gemini + CAN SLIM 방법론 기반 주식 분석 시스템

---

## 📌 프로젝트 개요

**Google Gemini API를 활용하여 주식 차트를 윌리엄 오닐(William J. O'Neil)의 CAN SLIM 방법론으로 자동 분석하고, 매수/관망/회피 판단을 제공하는 AI 기반 투자 분석 시스템**

- 기술적 분석 (차트 패턴, 이동평균, RS Rating)과 기본적 분석 (CAN SLIM 펀더멘털)을 통합
- AI가 O'Neil의 원문 규칙을 참조(RAG)하여 한국어로 종합 판단
- 미국 및 한국(KS/KQ) 주식 모두 지원
- **FastAPI 백엔드 연동을 위해 `core/` 모듈로 분리 완료**

---

## 📂 디렉토리 구조

```
hyochang/
│
├── main.py                      # 진입점 (python main.py로 실행)
├── cli.py                       # CLI 실행 로직 (main_v1, main_v2, main_compare, main)
├── requirements.txt
│
├── core/                        # 핵심 비즈니스 로직 (FastAPI에서 직접 import 가능)
│   ├── config.py                # 환경변수, 경로 상수
│   ├── data_fetcher.py          # 주가 데이터 수집, 이동평균 계산
│   ├── chart_generator.py       # 차트 생성 (O'Neil 스타일)
│   ├── ai_analyzer.py           # Gemini AI 분석 (V1, V2)
│   ├── result_manager.py        # 분석 결과 JSON 저장
│   ├── pattern_detector.py      # 코드 기반 패턴 감지 엔진
│   ├── fundamental_analyzer.py  # CAN SLIM 펀더멘털 오케스트레이터
│   ├── feedback_manager.py      # AI 분석 피드백 저장/학습
│   ├── history_analyzer.py      # 과거 분석 기록 컨텍스트 생성
│   ├── system_prompt.py         # Gemini 시스템 프롬프트 (O'Neil 페르소나)
│   └── version.py               # 버전 정보
│
├── canslim/                     # CAN SLIM 요소별 데이터 수집 모듈
│   ├── c_current_earnings.py    # C: 최근 분기 실적
│   ├── a_annual_earnings.py     # A: 연간 실적
│   ├── n_new_catalyst.py        # N: 신제품/촉매 (Gemini AI 조사)
│   ├── s_supply_demand.py       # S: 수급
│   ├── l_leader_laggard.py      # L: RS Rating
│   ├── i_institutional.py       # I: 기관 보유
│   └── m_market_direction.py    # M: 시장 방향 (Distribution Day)
│
├── frontend/
│   └── index.html               # 웹 UI (TradingView 차트 + AI 분석 패널)
├── results/                     # 분석 결과 자동 저장 (chart.png + JSON)
├── feedback/                    # 사용자 피드백 데이터 (AI 학습용)
├── scripts/
│   ├── quick_test.py            # 환경 사전 검증
│   └── list_models.py           # 사용 가능한 Gemini 모델 조회
└── prompt/
    └── chart_analysis_technical_spec.md  # 차트 분석 기술 명세 문서
```

---

## 🔄 분석 모드

### [1] V1 - Basic
AI가 차트 이미지를 직접 보고 시각적으로 분석합니다.

### [2] V2 - Enhanced (권장)
코드가 패턴을 먼저 감지하고, 펀더멘털 분석 후 AI가 종합 해석합니다.

```
[입력] 종목 코드 (Ticker)
   ↓
[패턴 감지] core/pattern_detector.py
   │     - Cup-with-Handle / Double Bottom / Flat Base / High Tight Flag
   │     - RS Rating 계산 (미국: S&P500, 한국KS: KOSPI, 한국KQ: KOSDAQ)
   │     - Volume Accumulation/Distribution 분석
   │     - Base Stage 카운팅
   ↓
[펀더멘털 분석] canslim/ 모듈들
   │     - C: 5개 분기 YoY EPS 성장률 + 가속/감속 판단
   │     - A: 5개년 연간 순이익 추이, ROE, P/E
   │     - N: Gemini AI로 신제품/신경영진/촉매 조사
   │     - S: 시가총액, 유통주식수, 부채비율, 자사주매입
   │     - L: RS Rating, 섹터/산업군
   │     - I: 기관 보유율 및 주요 기관 목록
   │     - M: S&P500/NASDAQ Distribution Day, 추세
   ↓
[차트 생성] core/chart_generator.py  →  results/chart.png
   ↓
[AI 종합 분석] core/ai_analyzer.py (Gemini gemini-2.5-flash)
   │     - 패턴 데이터 + 펀더멘털 데이터 + O'Neil 원문 규칙 통합
   │     - 한국어로 CAN SLIM 8개 섹션 분석 출력
   ↓
[출력] 한국어 투자 판단 리포트  →  results/{TICKER}_{TIMESTAMP}.json
   - BUY NOW / WATCH & WAIT / AVOID 결론
   - RS Rating, 패턴 품질, 구체적 가격 레벨
```

### [3] Compare - 다중 종목 비교
여러 종목을 입력하면 RS Rating, 패턴, 펀더멘털 핵심 지표를 테이블로 비교합니다.

---

## 🔌 FastAPI 연동 가이드 (백엔드 개발자용)

`core/` 모듈은 FastAPI에서 바로 import해서 사용할 수 있습니다.

### 핵심 함수 인터페이스

#### 1. 데이터 수집 — `core/data_fetcher.py`

```python
from core.data_fetcher import fetch_stock_data, calculate_moving_averages

df = fetch_stock_data(
    ticker="AAPL",       # str: 종목 코드 (e.g. "AAPL", "005930.KS")
    period="3y",         # str: 기간 ("1y", "2y", "3y")
    interval="1wk"       # str: "1wk" (주봉) | "1d" (일봉)
)
# 반환: pandas.DataFrame (OHLCV)

df = calculate_moving_averages(
    df=df,
    short_window=10,     # int: 단기 MA (주봉:10, 일봉:50)
    long_window=40       # int: 장기 MA (주봉:40, 일봉:200)
)
# 반환: MA50, MA200 컬럼이 추가된 DataFrame
```

#### 2. 차트 생성 — `core/chart_generator.py`

```python
from core.chart_generator import create_oneil_chart

create_oneil_chart(
    ticker="AAPL",
    df=df,
    output_path="results/chart.png",  # str: 저장 경로
    interval="1wk",                   # str: "1wk" | "1d"
    pivot_info={                      # dict | None: 피봇 포인트 표시
        "price": 150.0,
        "date": "2024-03-01",
        "pattern_type": "Cup with Handle"
    }
)
# 반환: None (output_path에 파일 저장)
```

#### 3. 패턴 감지 — `core/pattern_detector.py`

```python
from core.pattern_detector import run_pattern_detection

pattern_result = run_pattern_detection(df, ticker="AAPL")
# 반환: dict
# {
#   "best_pattern": {
#     "type": "Cup with Handle",
#     "quality_score": 82,        # 0-100
#     "pivot_point": 182.5,
#     "right_peak_date": "2024-03-01"
#   } | None,
#   "pattern_faults": ["handle too deep", ...],
#   "base_stage": {"estimated_stage": 2},
#   "volume_analysis": {"recent_volume_trend": "ACCUMULATION"},
#   "rs_analysis": {
#     "rs_rating": 87,            # 1-99
#     "rs_trend": "RISING",
#     "rs_new_high": True,
#     "interpretation": "..."
#   },
#   "summary": "..."              # AI 프롬프트용 요약 텍스트
# }
```

#### 4. 펀더멘털 분석 — `core/fundamental_analyzer.py`

```python
from core.fundamental_analyzer import analyze_fundamentals

fundamental_result = analyze_fundamentals(
    ticker="AAPL",
    rs_analysis=pattern_result["rs_analysis"]  # dict | None
)
# 반환: dict
# {
#   "prompt_text": "...",   # AI에 전달할 CAN SLIM 데이터 텍스트
#   "error": None | "..."
# }
```

#### 5. AI 분석 (V2) — `core/ai_analyzer.py`

```python
from core.ai_analyzer import analyze_chart_v2

analysis = analyze_chart_v2(
    image_path="results/chart.png",  # str: 차트 이미지 경로
    ticker="AAPL",
    df=df,                           # pandas.DataFrame
    pattern_result=pattern_result,   # dict: run_pattern_detection() 결과
    feedback_manager=None,           # FeedbackManager | None
    fundamental_result=fundamental_result,  # dict | None
    interval="1wk",                  # str: "1wk" | "1d"
    history_context=""               # str: 과거 분석 컨텍스트 (선택)
)
# 반환: str (마크다운 형식의 한국어 분석 텍스트)
# 포함 내용: Trend, Pattern, Volume, CAN SLIM 평가, Buy Point, Risk, FINAL VERDICT
```

#### 6. 결과 저장 — `core/result_manager.py`

```python
from core.result_manager import save_analysis_result

filepath = save_analysis_result(
    ticker="AAPL",
    analysis=analysis,               # str: AI 분석 텍스트
    interval="1wk",
    pattern_result=pattern_result,   # dict | None
    fundamental_result=fundamental_result,  # dict | None
    rs_info=pattern_result["rs_analysis"]   # dict | None
)
# 반환: str (저장된 JSON 파일 경로)
# 저장 위치: results/{TICKER}_{YYYY-MM-DD_HH-MM-SS}.json
```

### 전체 V2 분석 플로우 예시 (FastAPI route용)

```python
from core.data_fetcher import fetch_stock_data, calculate_moving_averages
from core.chart_generator import create_oneil_chart
from core.pattern_detector import run_pattern_detection
from core.fundamental_analyzer import analyze_fundamentals
from core.ai_analyzer import analyze_chart_v2
from core.result_manager import save_analysis_result
from core.config import CHART_OUTPUT_PATH

async def analyze(ticker: str, interval: str = "1wk"):
    df = fetch_stock_data(ticker, interval=interval)
    df = calculate_moving_averages(df)
    pattern_result = run_pattern_detection(df, ticker)
    fundamental_result = analyze_fundamentals(ticker, rs_analysis=pattern_result["rs_analysis"])
    create_oneil_chart(ticker, df, interval=interval)
    analysis = analyze_chart_v2(CHART_OUTPUT_PATH, ticker, df, pattern_result,
                                 fundamental_result=fundamental_result, interval=interval)
    filepath = save_analysis_result(ticker, analysis, interval, pattern_result, fundamental_result)
    return {"analysis": analysis, "result_file": filepath}
```

> **주의:** `analyze_chart_v2`는 Gemini API를 호출하므로 **10~30초** 소요됩니다.
> FastAPI에서는 `BackgroundTasks` 또는 `asyncio.to_thread()`로 비동기 처리를 권장합니다.

---

## ⚙️ 설치 및 실행

### 1. 환경 설정

```bash
python -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows

pip install -r requirements.txt
```

### 2. API 키 설정

```bash
cp .env.example .env
# .env 파일을 열고 GEMINI_API_KEY 입력
```

### 3. CLI 실행

```bash
python main.py
```

### 4. FastAPI 서버 실행 (웹 UI 연동)

```bash
uvicorn api:app --reload
# → http://localhost:8000
# → frontend/index.html을 브라우저에서 열어 사용
```

### 5. 사전 환경 검증

```bash
python scripts/quick_test.py
```

---

## 📊 분석 결과 형식

`results/{TICKER}_{TIMESTAMP}.json`

```json
{
  "ticker": "AAPL",
  "timestamp": "2026-02-16_20-34-36",
  "interval": "weekly",
  "verdict": "WATCH & WAIT",
  "ai_analysis": "## CHART ANALYSIS: AAPL\n...",
  "pattern_detection": { ... },
  "fundamental": { ... },
  "rs_info": {
    "rs_rating": 72,
    "rs_trend": "NEUTRAL",
    "rs_new_high": false
  }
}
```

---

## 🔑 CAN SLIM 방법론

| 요소 | 의미 | O'Neil 기준 |
|------|------|------------|
| **C** | Current Quarterly Earnings | 최근 분기 EPS YoY 25-50%+ 성장 |
| **A** | Annual Earnings | 최근 3-5년 연속 25%+ 연간 성장, ROE 17%+ |
| **N** | New Products/Management/Highs | 혁신적 신제품, 새 경영진, 신고가 돌파 |
| **S** | Supply & Demand | 소형주 선호, 낮은 부채, 자사주매입은 긍정 신호 |
| **L** | Leader or Laggard | RS Rating 85+ (시장 선도주) |
| **I** | Institutional Sponsorship | 우수 기관투자자 보유, 과다보유는 위험 신호 |
| **M** | Market Direction | 시장 방향이 투자의 50%; Distribution Day 5개+ = 정점 신호 |

---

## 📦 주요 의존성

| 라이브러리 | 용도 |
|-----------|------|
| `yfinance` | 주가 데이터 수집 (Yahoo Finance) |
| `mplfinance` | 금융 차트 생성 |
| `pandas` | 데이터 처리 및 시계열 분석 |
| `google-genai` | Gemini AI API |
| `python-dotenv` | `.env` 파일 자동 로딩 |
| `Pillow` | 차트 이미지 처리 |
| `fastapi` | REST API 서버 (웹 UI 백엔드) |
| `uvicorn` | FastAPI ASGI 서버 |

---

## 📝 버전 히스토리

| 버전 | 날짜 | 주요 변경사항 |
|------|------|-------------|
| **v2.1.0** | 2026-02-16 | `core/` 모듈 분리, FastAPI 연동 준비, 결과물 `results/` 통합 저장 |
| **v2.0.0** | 2026-02-05 | V2 패턴 감지 엔진 추가, 펀더멘털 분석 통합 |
| **v1.0.0** | 2026-01-01 | V1 기본 이미지 분석 |

---

## ⚠️ 면책 조항

이 프로젝트는 **교육 목적**으로 작성되었습니다.
투자 판단은 본인 책임이며, AI 분석 결과는 **참고용**입니다.
실제 투자 전 반드시 본인의 독립적인 판단과 전문가 조언을 구하십시오.

---

**Created by:** hyochang team
**Last Updated:** 2026-02-17
**License:** MIT (Educational Purpose)
