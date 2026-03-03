# CLAUDE.md - William O'Neil AI Investment Assistant

## Project Overview

William O'Neil의 CAN SLIM 방법론을 적용한 AI 주식 분석 시스템 (v2.1.0).
Google Gemini API(멀티모달)를 사용해 차트 이미지 + 기본적 분석 데이터를 통합 평가.
결과는 **한국어**로 출력 (BUY NOW / WATCH & WAIT / AVOID).

## Architecture

```
backend/services/chart_canslim_service/
├── core/               # 핵심 비즈니스 로직 (FastAPI에서도 import 가능)
│   ├── config.py           # 환경변수, API 키, 경로 설정
│   ├── data_fetcher.py     # Yahoo Finance 데이터 수집, 이동평균 계산
│   ├── pattern_detector.py # 코드 기반 패턴 감지 (Cup-with-Handle 등) + RS Rating
│   ├── chart_generator.py  # O'Neil 스타일 차트 시각화 (mplfinance)
│   ├── ai_analyzer.py      # Gemini API 연동 (차트 이미지 + 텍스트 분석)
│   ├── fundamental_analyzer.py  # CAN SLIM 오케스트레이터 (canslim/* 호출)
│   ├── result_manager.py   # JSON 결과 저장 (results/TICKER_TIMESTAMP.json)
│   ├── feedback_manager.py # 사용자 피드백 수집
│   ├── history_analyzer.py # 과거 분석 컨텍스트 구성
│   ├── system_prompt.py    # William O'Neil 페르소나 프롬프트 (307줄)
│   └── version.py          # 버전 관리 (2.1.0)
│
├── canslim/            # CAN SLIM 7개 요소 개별 모듈
│   ├── c_current_earnings.py   # C: 분기 EPS YoY 성장
│   ├── a_annual_earnings.py    # A: 5년 연간 추세 + ROE + P/E
│   ├── n_new_catalyst.py       # N: 혁신/신제품/신경영 (AI 조사)
│   ├── s_supply_demand.py      # S: 시총, 부채비율, 자사주 매입
│   ├── l_leader_laggard.py     # L: RS Rating (vs S&P500/KOSPI/KOSDAQ)
│   ├── i_institutional.py      # I: 기관 소유 현황
│   └── m_market_direction.py   # M: S&P500 Distribution Days
│
├── cli.py              # CLI 진입점 (V1/V2/Compare 모드)
├── api.py              # FastAPI 서버
├── main.py             # 하위 호환성 레이어 (cli.py 위임)
└── results/            # 생성된 차트(PNG) + 분석 결과(JSON) 저장
```

## Tech Stack

- **Python 3.14+**
- **AI**: `google-genai ≥1.0.0` → Gemini 2.5 Flash (멀티모달)
- **Data**: `yfinance ≥0.2.36`, `pandas ≥2.0.0`
- **Chart**: `mplfinance ≥0.12.9b7`, `matplotlib ≥3.8.0`
- **API Server**: FastAPI + uvicorn
- **Env**: `python-dotenv` (.env 파일, `GEMINI_API_KEY` 필수)

## Development Commands

```bash
# 환경 활성화
source venv/bin/activate

# CLI 실행 (대화형 메뉴)
python main.py

# FastAPI 서버 실행
uvicorn api:app --reload

# 환경 사전 점검
python scripts/quick_test.py

# 사용 가능한 Gemini 모델 확인
python scripts/list_models.py
```

## Key Data Flows

### V2 분석 플로우 (핵심)
```
Ticker 입력
  → fetch_stock_data() + calculate_moving_averages()   [data_fetcher.py]
  → run_pattern_detection()                             [pattern_detector.py]
  → analyze_fundamentals()                              [fundamental_analyzer.py → canslim/*]
  → create_oneil_chart()                                [chart_generator.py → results/chart.png]
  → analyze_chart_v2(chart, data, patterns, fundamentals) [ai_analyzer.py → Gemini]
  → save_analysis_result()                              [result_manager.py → results/JSON]
```

### API 엔드포인트
```
POST /analyze  { "ticker": "AAPL", "mode": "v2", "interval": "1wk" }
```

## Return Data Structures

```python
# 패턴 감지 결과
pattern_result = {
    "best_pattern": {...},
    "pattern_faults": [...],
    "base_stage": {...},
    "volume_analysis": {...},
    "rs_analysis": {...}
}

# 기본적 분석 결과
fundamental_result = {
    "data": {...},
    "prompt_text": str,
    "error": None
}

# 저장 JSON 구조
result_json = {
    "ticker", "timestamp", "interval", "verdict",
    "ai_analysis", "pattern_detection", "fundamental", "rs_info"
}
```

## Coding Conventions

- **언어**: 한국어 주석 + 한국어 출력 (print 포함)
- **함수 시그니처**: `def func(ticker: str, param: type = default) -> Dict:`
- **에러 처리**: try-except with `[ERROR]` 콘솔 출력; 예외는 results에 로깅
- **타임스탬프**: `YYYY-MM-DD_HH-MM-SS` 형식 (파일명에 사용)
- **시장 지원**: US 주식 (AAPL), 한국 주식 (005930.KS, 035720.KQ)
- **모듈 독립성**: 각 core/* 모듈은 독립적으로 import 가능해야 함

## AI Prompting Approach

- **시스템 프롬프트**: William O'Neil 페르소나 (`core/system_prompt.py`, 307줄)
- **사용자 프롬프트**: 데이터 요약 + 패턴 데이터 + 기본적 분석 (텍스트 + 이미지)
- **출력 형식**: 마크다운 (`## CHART ANALYSIS`, `### PATTERN` 등)
- **CAN SLIM 평가**: 점수화 없이 AI가 O'Neil 원칙에 따라 통합 판단

## Environment Setup

```bash
# .env 파일에 필요한 변수
GEMINI_API_KEY=your_key_here  # https://aistudio.google.com/app/apikey
```

## Common Pitfalls

- `GEMINI_API_KEY` 없으면 `core/config.py`에서 즉시 실패
- 한국 주식은 `.KS` (KOSPI) 또는 `.KQ` (KOSDAQ) suffix 필수
- `results/` 디렉토리는 자동 생성됨 (git-ignored)
- 차트 생성 전에 이동평균 계산(`calculate_moving_averages`) 반드시 선행
- `canslim/n_new_catalyst.py`는 AI 조사를 사용하므로 추가 API 호출 발생

## Version History

현재 v2.1.0. 변경사항은 `core/version.py` 참조.
