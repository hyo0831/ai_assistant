# chart_canslim_service - 아키텍처 문서

> ⚠️ **레거시 서비스**: 프로덕션은 `integrated_investment_service`를 사용합니다.

---

## 전체 아키텍처

```
사용자 입력 (종목 코드)
       │
       ▼
┌─────────────────────────────┐
│  STEP 1: 데이터 수집         │
│  yfinance → OHLCV DataFrame │
│  - 주봉: 3년 (period=3y)    │
│  - 일봉: 1년 (period=1y)    │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│  STEP 2: 전처리              │
│  - 이동평균 계산             │
│    주봉: 10주, 40주          │
│    일봉: 50일, 200일         │
└──────────────┬──────────────┘
               │
       ┌───────┴────────┐
       ▼                ▼
  ┌─────────┐     ┌──────────────────────┐
  │  V1 모드 │     │      V2 모드 (권장)   │
  │ AI 이미지│     │  코드 패턴 감지 먼저  │
  │  직접분석│     │  → AI 해석           │
  └────┬────┘     └──────────┬───────────┘
       │                     │
       │          ┌──────────┴──────────┐
       │          ▼                     ▼
       │  ┌──────────────┐   ┌─────────────────┐
       │  │ 패턴 감지     │   │ 펀더멘털 분석    │
       │  │ pattern_     │   │ fundamental_    │
       │  │ detector.py  │   │ analyzer.py     │
       │  │              │   │ → canslim/ 모듈 │
       │  └──────┬───────┘   └──────┬──────────┘
       │         └─────────┬────────┘
       │                   ▼
       │         ┌─────────────────┐
       │         │  차트 생성       │
       │         │  chart_         │
       │         │  generator.py   │
       │         └──────┬──────────┘
       └────────────────┘
                        │
                        ▼
               ┌────────────────┐
               │  AI 분석        │
               │  ai_analyzer.py│
               │  (Gemini only) │
               └──────┬─────────┘
                      │
                      ▼
               ┌────────────────┐
               │  결과 저장      │
               │  result_       │
               │  manager.py    │
               │  → JSON + PNG  │
               └────────────────┘
```

---

## 핵심 모듈

### core/pattern_detector.py

패턴 감지 알고리즘:
- **Cup-with-Handle**: U자 + 핸들, 깊이 12-33%, 기간 7-65주
- **Flat Base**: 횡보 5주+, 가격 변동 15% 이내
- **Double Bottom**: W자, 두 저점 차이 4% 이내
- **High Tight Flag**: 8주 내 100%+ 상승 후 10-25% 조정

각 패턴은 0-100점 품질 점수로 평가.

### core/ai_analyzer.py

- V1: 차트 이미지만 Gemini에 전달
- V2: 패턴 데이터 + 펀더멘털 텍스트 + 차트 이미지 통합 전달
- **Gemini only** (멀티 프로바이더는 `integrated_investment_service/trading/ai_analyzer.py` 참조)

### canslim/ 모듈 특징

`integrated_investment_service/trading/canslim/`보다 더 상세한 분석 포함:
- `s_supply_demand.py`: Accumulation/Distribution 분석, 부채 추이, 전환사채 감지
- `l_leader_laggard.py`: RS 티어 분류, 섹터 ETF 비교, 하락폭 분석, 복원력 지표

---

## 데이터 흐름 예시

```python
# V2 분석 플로우
df = fetch_stock_data("AAPL", period="3y", interval="1wk")
df = calculate_moving_averages(df)
pattern_result = run_pattern_detection(df, ticker="AAPL")
fundamental_result = analyze_fundamentals("AAPL", rs_analysis=pattern_result["rs_analysis"])
create_oneil_chart("AAPL", df, output_path="results/chart.png")
analysis = analyze_chart_v2("results/chart.png", "AAPL", df, pattern_result,
                            fundamental_result=fundamental_result)
save_analysis_result("AAPL", analysis, "1wk", pattern_result, fundamental_result)
```

---

## 기술 스택

- **Python 3.11+**
- **AI**: Gemini 2.5 Flash (`google-genai`)
- **Data**: yfinance, pandas
- **Chart**: mplfinance, matplotlib
- **API**: FastAPI + uvicorn (단독 실행용)
