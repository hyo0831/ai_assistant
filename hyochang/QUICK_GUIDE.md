# William O'Neil AI Assistant - 빠른 가이드

## 🎯 한 줄 요약
**윌리엄 오닐의 CAN SLIM 투자 방법론을 AI로 자동화한 주식 분석 도구**

---

## 🚀 빠른 시작

### 1. 환경 설정
```bash
# API 키 설정
cp .env.template .env
# .env 파일에 GEMINI_API_KEY 입력

# 패키지 설치
pip install -r requirements.txt
```

### 2. 실행
```bash
python main.py
```

### 3. 사용
```
Select mode (1 or 2): 2          # V2 Enhanced 모드 선택
Enter ticker symbol: AAPL        # 종목 코드 입력
```

---

## 📊 어떻게 작동하나?

### 간단 버전
```
입력 → 데이터 수집 → 패턴 감지 → AI 분석 → 매수/관망/회피 판단
```

### 상세 버전

#### 1단계: 데이터 수집 (Yahoo Finance)
```python
# 주봉 3년치 데이터 다운로드
df = yf.download("AAPL", period="3y", interval="1wk")

# 결과: OHLCV 데이터
# Date       | Open | High | Low | Close | Volume
# 2023-01-09 | 130  | 133  | 129 | 130   | 70M
```

#### 2단계: 이동평균선 계산
```python
# 주봉: 10주, 40주, 200주 이평
df['MA10'] = df['Close'].rolling(10).mean()
df['MA40'] = df['Close'].rolling(40).mean()
```

#### 3단계: 패턴 감지 (V2만)
```python
# 알고리즘으로 패턴 자동 감지
pattern = detect_cup_with_handle(df)

# 결과
{
  "pattern": "Cup-with-Handle",
  "quality": 100,
  "pivot_point": 69.55,
  "base_stage": 1
}
```

#### 4단계: 차트 생성
```python
# mplfinance로 전문적인 차트 생성
create_chart(df)
# → chart.png 저장
```

#### 5단계: AI 분석
```python
# Gemini Vision이 차트 + 패턴 데이터 분석
analysis = gemini.analyze(chart_image, pattern_data)

# 결과: "WATCH - 너무 올랐음, 새 베이스 기다려"
```

---

## 🔍 두 가지 모드

### V1 - Basic (기본)
```
차트만 보고 AI가 직접 분석
```
- 장점: 간단함
- 단점: 정확도 낮음

### V2 - Enhanced (추천)
```
코드가 먼저 패턴 감지 → AI가 검증/해석
```
- 장점: 높은 정확도, 정밀한 수치
- 단점: 복잡함

---

## 📈 분석 결과 해석

### BUY (매수)
```
✅ 패턴 완성
✅ 매수 포인트 근처 (5% 이내)
✅ 거래량 증가
→ 지금 매수하세요!
```

### WATCH (관망)
```
🔄 패턴 형성 중
⏳ 매수 포인트 대기
→ 지켜보다가 적절한 타이밍에 매수
```

### AVOID (회피)
```
❌ 너무 많이 올랐음
❌ 패턴 깨짐
❌ 하락 추세
→ 매수하지 마세요
```

---

## 🎯 윌리엄 오닐 핵심 원칙

### 1. CAN SLIM
- **C**urrent Earnings (현재 실적)
- **A**nnual Earnings (연간 실적)
- **N**ew Product/Service (신제품/서비스)
- **S**upply & Demand (수급 - 거래량!)
- **L**eader or Laggard (리더 종목)
- **I**nstitutional Sponsorship (기관 매수)
- **M**arket Direction (시장 방향)

### 2. 차트 패턴
- **Cup with Handle**: U자 + 작은 핸들
- **Flat Base**: 횡보 5주 이상
- **Double Bottom**: W자 형태
- **High Tight Flag**: 가파른 상승 후 짧은 조정

### 3. 리스크 관리
- **7-8% 손절**: 매수 후 7-8% 하락 시 무조건 손절
- **5% 룰**: 매수 포인트에서 5% 이상 떨어진 곳에서 추격 매수 금지
- **Stage 1 선호**: 첫 번째 베이스가 가장 성공 확률 높음

---

## 🛠️ 기술 스택

### 데이터
- **yfinance**: Yahoo Finance API
- **pandas**: 데이터 처리

### 차트
- **mplfinance**: 전문 금융 차트
- **matplotlib**: 기본 플로팅

### AI
- **Google Gemini 2.5 Flash**: Vision + Text 분석

### 알고리즘
- **numpy**: 수치 계산
- **scipy**: Spline 보간

---

## 📁 주요 파일

| 파일 | 역할 |
|------|------|
| `main.py` | 메인 실행 파일 (V1/V2) |
| `pattern_detector.py` | 패턴 감지 알고리즘 |
| `system_prompt.py` | AI 페르소나 |
| `feedback_manager.py` | 피드백 수집 |
| `.env` | API 키 (절대 커밋 금지!) |
| `chart.png` | 생성된 차트 |

---

## 💡 사용 예시

### 예시 1: 애플(AAPL) 분석
```bash
$ python main.py

Select mode: 2
Enter ticker: AAPL

Result:
✅ Pattern: Cup-with-Handle (100점)
✅ Pivot: $175.50
✅ Current: $172.30 (-1.8%)
→ WATCH: 매수 포인트 근처, 돌파 대기
```

### 예시 2: 엔비디아(NVDA) 분석
```bash
Result:
⚠️ Pattern: Flat Base (70점)
⚠️ Fault: V-shaped bottom
⚠️ Pivot: $184.50
⚠️ Current: $171.90 (-6.8%)
→ WATCH: 베이스 형성 중
```

### 예시 3: 코카콜라(KO) 분석
```bash
Result:
❌ Pattern: Cup-with-Handle (100점)
❌ Pivot: $69.55
❌ Current: $78.60 (+13%)
→ AVOID: 너무 많이 올랐음, 늦었음
```

---

## ⚠️ 주의사항

### 데이터 제한
- **신규 상장주**: 데이터 부족으로 분석 제한적
- **주봉 데이터**: 최소 50주 필요
- **200주 이평**: 3년 데이터로는 부족 (4년 필요)

### API 제한
- **Gemini 무료 티어**: 하루 20회 제한
- **초과 시**: 54초 대기 후 재시도

### 한계
- **과거 데이터 기반**: 미래 보장 안함
- **AI 판단**: 100% 정확하지 않음
- **투자 책임**: 본인에게 있음

---

## 🔧 트러블슈팅

### 문제: API 키 오류
```
ValueError: GEMINI_API_KEY is not set
```
**해결:** .env 파일에 API 키 입력

### 문제: 데이터 없음
```
[ERROR] No data found for ticker
```
**해결:** 티커 심볼 확인 (예: 삼성전자 = 005930.KS)

### 문제: 폰트 경고
```
UserWarning: Glyph missing from font
```
**해결:** 영어 텍스트만 사용 (이미 적용됨)

### 문제: 차트 생성 실패
```
ValueError: zero-size array
```
**해결:** 데이터가 너무 적음, 더 긴 기간 사용

---

## 📚 더 알아보기

- **상세 문서**: [ARCHITECTURE.md](ARCHITECTURE.md)
- **윌리엄 오닐 책**: "How to Make Money in Stocks"
- **CAN SLIM**: [Investor's Business Daily](https://www.investors.com)

---

## 🤝 기여하기

이 프로젝트는 MVP 단계입니다. 피드백 환영합니다!

**개선 아이디어:**
- [ ] 웹 UI 개발
- [ ] 더 많은 패턴 추가
- [ ] 백테스팅 기능
- [ ] 포트폴리오 관리

---

## 📄 라이선스

교육/연구 목적으로만 사용하세요.
투자 손실에 대한 책임은 본인에게 있습니다.

---

**Happy Investing! 📈**
