# chart_canslim_service - 빠른 가이드

> ⚠️ **레거시 서비스**: 프로덕션은 `integrated_investment_service`를 사용합니다.

---

## 빠른 시작

```bash
# API 키 설정
cp .env.example .env
# .env 파일에 GEMINI_API_KEY 입력

# 패키지 설치
pip install -r requirements.txt

# 실행
python main.py
```

```
Select mode (1 or 2): 2   # V2 Enhanced 모드 권장
Enter ticker symbol: AAPL
```

---

## 분석 모드

### V1 - Basic
차트 이미지만 AI에 전달해서 시각적으로 분석. 간단하지만 정확도 낮음.

### V2 - Enhanced (권장)
코드로 패턴 먼저 감지 → AI가 데이터 기반으로 해석. 정확도 높음.

---

## 결과 해석

| 판정 | 의미 |
|------|------|
| **BUY NOW** | 패턴 완성 + 매수 포인트 5% 이내 + 거래량 증가 |
| **WATCH & WAIT** | 패턴 형성 중 또는 매수 포인트 대기 |
| **AVOID** | 과도 상승, 패턴 붕괴, 하락 추세 |

---

## CAN SLIM 핵심 원칙

- **C** Current Earnings: 분기 EPS YoY 25%+
- **A** Annual Earnings: 3-5년 연속 25%+, ROE 17%+
- **N** New Catalyst: 신제품/신경영/52주 신고가
- **S** Supply & Demand: 소형 유통주식수, 낮은 부채
- **L** Leader: RS Rating 85+
- **I** Institutional: 우량 기관 보유 증가
- **M** Market: S&P500 상승 추세

리스크 관리: 7-8% 손절, 매수 포인트 5% 초과 추격매수 금지

---

## 주요 파일

| 파일 | 역할 |
|------|------|
| `main.py` | 진입점 |
| `core/pattern_detector.py` | 패턴 감지 알고리즘 |
| `core/ai_analyzer.py` | Gemini AI 분석 |
| `core/fundamental_analyzer.py` | CAN SLIM 오케스트레이터 |
| `canslim/` | CAN SLIM 7개 요소 모듈 |
| `results/` | 차트(PNG) + 분석 결과(JSON) |

---

## 트러블슈팅

| 증상 | 해결 |
|------|------|
| `GEMINI_API_KEY is not set` | .env 파일에 키 입력 |
| `No data found for ticker` | 티커 확인 (한국: `005930.KS`) |
| `zero-size array` | 데이터 부족, 더 긴 기간 사용 |

---

**참고**: 교육 목적 도구. 투자 손실 책임은 본인에게 있습니다.
