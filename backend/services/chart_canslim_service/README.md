# chart_canslim_service

> ⚠️ **레거시 서비스 (Standalone 프로토타입)**
> 프로덕션은 `integrated_investment_service`를 사용합니다.
> 차트 분석 로직은 `integrated_investment_service/trading/`으로 이식·발전되었습니다.

William O'Neil의 **CAN SLIM** 방법론을 기반으로 주식 차트를 AI로 분석하는 독립 실행형 서비스입니다.

---

## 분석 파이프라인

```
Ticker 입력
  → 데이터 수집 (Yahoo Finance, 주봉 3년)
  → 패턴 감지 (Cup-with-Handle / Flat Base / Double Bottom / High Tight Flag)
  → 펀더멘털 수집 (CAN SLIM 7개 요소)
  → 차트 생성 (O'Neil 스타일)
  → AI 분석 (Gemini Vision)
  → BUY NOW / WATCH & WAIT / AVOID 판정
```

---

## 디렉토리 구조

```
chart_canslim_service/
├── core/                        # 핵심 비즈니스 로직
│   ├── data_fetcher.py          # Yahoo Finance 데이터 수집
│   ├── pattern_detector.py      # 패턴 감지 + RS Rating
│   ├── chart_generator.py       # O'Neil 스타일 차트 생성
│   ├── ai_analyzer.py           # Gemini AI 분석 (V1/V2)
│   ├── fundamental_analyzer.py  # CAN SLIM 오케스트레이터
│   ├── result_manager.py        # JSON 결과 저장
│   ├── system_prompt.py         # William O'Neil 페르소나 프롬프트
│   └── ...
├── canslim/                     # CAN SLIM 요소별 데이터 수집
│   ├── c_current_earnings.py    # C: 분기 EPS 성장
│   ├── a_annual_earnings.py     # A: 연간 EPS 성장
│   ├── n_new_catalyst.py        # N: 신촉매 (AI 조사)
│   ├── s_supply_demand.py       # S: 수급 (A/D 분석 포함)
│   ├── l_leader_laggard.py      # L: RS Rating + 섹터 비교
│   ├── i_institutional.py       # I: 기관 보유
│   └── m_market_direction.py    # M: 시장 방향
├── cli.py                       # CLI 진입점
├── api.py                       # 단독 FastAPI 서버 (레거시)
├── main.py                      # 진입점 (cli.py 위임)
├── results/                     # 차트(PNG) + 분석 결과(JSON)
└── .env.example
```

---

## 실행

```bash
# 의존성 설치
pip install -r requirements.txt

# 환경변수 설정
cp .env.example .env  # GEMINI_API_KEY 입력

# CLI 실행
python main.py
```

루트에서 실행할 경우: `make install-chart` / `make run-chart-cli`

---

## 분석 모드

| 모드 | 설명 |
|------|------|
| **V1** | AI가 차트 이미지를 직접 시각 분석 |
| **V2** (권장) | 코드가 패턴 감지 → AI가 데이터 기반으로 종합 해석 |
| **Compare** | 여러 종목 RS Rating / 패턴 비교 |

---

## CAN SLIM 기준

| 항목 | 기준 |
|------|------|
| C – Current Earnings | 분기 EPS YoY 25%+ |
| A – Annual Earnings | 3-5년 연속 25%+, ROE 17%+ |
| N – New Catalyst | 신제품/신경영/52주 신고가 |
| S – Supply & Demand | 소형 유통주식수, 낮은 부채, 자사주매입 |
| L – Leader | RS Rating 85+ |
| I – Institutional | 우량 기관 보유 증가 |
| M – Market | S&P500 상승 추세, Distribution Day 5개 미만 |

---

## 주의사항

- 교육/연구 목적으로만 사용
- AI 분석 결과는 참고용이며 투자 결정은 본인 책임
- Yahoo Finance 데이터 기반으로 실시간 정확도 한계 있음
