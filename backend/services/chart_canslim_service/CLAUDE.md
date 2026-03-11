# CLAUDE.md - chart_canslim_service

> ⚠️ **레거시 서비스**: 이 서비스는 독립 실행형 프로토타입입니다.
> 프로덕션 서비스는 `integrated_investment_service`를 사용합니다.
> 차트 분석 로직은 `integrated_investment_service/trading/`으로 이식되어 멀티 AI 프로바이더(Gemini/OpenAI/Claude)를 지원합니다.

## Project Overview

William O'Neil의 CAN SLIM 방법론을 적용한 AI 주식 분석 시스템 (standalone).
Google Gemini API(멀티모달)를 사용해 차트 이미지 + 기본적 분석 데이터를 통합 평가.
결과는 **한국어**로 출력 (BUY NOW / WATCH & WAIT / AVOID).

**AI 프로바이더**: Gemini only (멀티 프로바이더는 integrated_investment_service/trading 참조)

## Architecture

```
backend/services/chart_canslim_service/
├── core/               # 핵심 비즈니스 로직
│   ├── config.py           # 환경변수, API 키, 경로 설정
│   ├── data_fetcher.py     # Yahoo Finance 데이터 수집, 이동평균 계산
│   ├── pattern_detector.py # 코드 기반 패턴 감지 (Cup-with-Handle 등) + RS Rating
│   ├── chart_generator.py  # O'Neil 스타일 차트 시각화 (mplfinance)
│   ├── ai_analyzer.py      # Gemini API 연동 (차트 이미지 + 텍스트 분석)
│   ├── fundamental_analyzer.py  # CAN SLIM 오케스트레이터 (canslim/* 호출)
│   ├── result_manager.py   # JSON 결과 저장 (results/TICKER_TIMESTAMP.json)
│   ├── feedback_manager.py # 사용자 피드백 수집
│   ├── history_analyzer.py # 과거 분석 컨텍스트 구성
│   ├── system_prompt.py    # William O'Neil 페르소나 프롬프트
│   └── version.py          # 버전 관리
│
├── canslim/            # CAN SLIM 7개 요소 개별 모듈 (integrated 버전보다 상세)
│   ├── c_current_earnings.py   # C: 분기 EPS YoY 성장
│   ├── a_annual_earnings.py    # A: 5년 연간 추세 + ROE + P/E
│   ├── n_new_catalyst.py       # N: 혁신/신제품/신경영 (AI 조사)
│   ├── s_supply_demand.py      # S: 시총, 부채비율, A/D 분석 (상세)
│   ├── l_leader_laggard.py     # L: RS Rating + 섹터 비교 + 하락폭 분석 (상세)
│   ├── i_institutional.py      # I: 기관 소유 현황
│   └── m_market_direction.py   # M: S&P500 Distribution Days
│
├── cli.py              # CLI 진입점 (V1/V2/Compare 모드)
├── api.py              # 단독 FastAPI 서버 (:8000, 레거시)
├── main.py             # 하위 호환성 레이어 (cli.py 위임)
└── results/            # 생성된 차트(PNG) + 분석 결과(JSON) 저장
```

## Development Commands

```bash
# CLI 실행 (대화형 메뉴)
python main.py

# 단독 FastAPI 서버 실행 (레거시)
uvicorn api:app --reload

# 환경 사전 점검
python scripts/quick_test.py
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

## Environment Setup

```bash
cp .env.example .env
# GEMINI_API_KEY 입력
```

## Common Pitfalls

- `GEMINI_API_KEY` 없으면 `core/config.py`에서 즉시 실패
- 한국 주식은 `.KS` (KOSPI) 또는 `.KQ` (KOSDAQ) suffix 필수
- `results/` 디렉토리는 자동 생성됨
- 차트 생성 전에 `calculate_moving_averages` 반드시 선행
