# William O'Neil AI Investment Assistant - 시스템 구조 문서

## 📋 목차
1. [개요](#개요)
2. [전체 아키텍처](#전체-아키텍처)
3. [데이터 흐름](#데이터-흐름)
4. [핵심 컴포넌트](#핵심-컴포넌트)
5. [분석 모드](#분석-모드)
6. [기술 스택](#기술-스택)
7. [파일 구조](#파일-구조)

---

## 개요

### 프로젝트 목적
전설적인 투자자 윌리엄 오닐(William O'Neil)의 CAN SLIM 투자 방법론을 AI로 자동화하여, 주식 차트를 분석하고 매수/매도 시점을 판단하는 도구

### 핵심 가치
- **자동화된 패턴 인식**: Cup with Handle, Flat Base, Double Bottom 등
- **AI 해석**: Google Gemini가 윌리엄 오닐 페르소나로 차트 분석
- **실시간 데이터**: Yahoo Finance API를 통한 실시간 주가 데이터
- **시각화**: 패턴을 오버레이한 전문적인 차트 생성

---

## 전체 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                    사용자 입력                                │
│              (종목 코드: AAPL, NVDA, 001510.KS...)           │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  STEP 1: 데이터 수집                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Yahoo Finance API (yfinance)                        │  │
│  │  - 주봉 데이터: 3년 (period="3y", interval="1wk")    │  │
│  │  - 일봉 데이터: 1년 (period="1y", interval="1d")     │  │
│  │  - OHLCV 데이터: Open, High, Low, Close, Volume      │  │
│  └──────────────────────────────────────────────────────┘  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                STEP 2: 데이터 전처리                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  1. 주봉 리샘플링 (일봉 → 주봉)                       │  │
│  │  2. 이동평균선 계산                                   │  │
│  │     - 주봉: 10주, 40주, 200주 MA                     │  │
│  │     - 일봉: 50일, 200일 MA                           │  │
│  │  3. 데이터 정제 (NaN 처리, 타임존 조정)               │  │
│  └──────────────────────────────────────────────────────┘  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                STEP 3: 차트 생성                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  mplfinance 라이브러리 사용                           │  │
│  │  - 캔들스틱 차트                                      │  │
│  │  - 이동평균선 오버레이                                │  │
│  │  - 거래량 바 차트                                     │  │
│  │  - 윌리엄 오닐 스타일 (Linear Scale)                 │  │
│  │  → chart.png 저장                                    │  │
│  └──────────────────────────────────────────────────────┘  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
           ┌───────────┴────────────┐
           │                        │
           ▼                        ▼
    ┌─────────────┐         ┌──────────────┐
    │  V1 모드    │         │   V2 모드    │
    │  (기본)     │         │  (향상됨)    │
    └──────┬──────┘         └──────┬───────┘
           │                       │
           ▼                       ▼
┌─────────────────────┐   ┌─────────────────────┐
│  AI 이미지 분석      │   │ 코드 패턴 감지       │
│  (Gemini Vision)    │   │ (pattern_detector)  │
│                     │   │                     │
│  - 차트 이미지 전송  │   │ - 알고리즘 기반     │
│  - AI가 직접 해석   │   │ - 수치 계산         │
│  - 패턴 인식        │   │ - 정밀 분석         │
└──────┬──────────────┘   └──────┬──────────────┘
       │                         │
       │                         ▼
       │              ┌─────────────────────┐
       │              │  AI 해석             │
       │              │  (Gemini)           │
       │              │                     │
       │              │ - 패턴 검증         │
       │              │ - 투자 판단         │
       └──────────────┤ - 맥락 이해         │
                      └──────┬──────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                STEP 4: 결과 생성                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  분석 결과 (JSON)                                     │  │
│  │  {                                                   │  │
│  │    "pattern": "Cup with Handle",                     │  │
│  │    "quality": 100,                                   │  │
│  │    "pivot_point": 69.55,                             │  │
│  │    "action": "BUY / WATCH / AVOID",                  │  │
│  │    "confidence": "HIGH / MEDIUM / LOW",              │  │
│  │    "analysis": "상세 분석 텍스트..."                  │  │
│  │  }                                                   │  │
│  └──────────────────────────────────────────────────────┘  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                STEP 5: 시각화 (V2만)                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  패턴 오버레이 차트                                   │  │
│  │  - 패턴 포인트 마킹                                   │  │
│  │  - Cubic Spline 보간으로 부드러운 곡선                │  │
│  │  - Buy Point, Stop Loss 표시                        │  │
│  │  → final_analysis.png (또는 chart.png)               │  │
│  └──────────────────────────────────────────────────────┘  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    최종 출력                                  │
│  - 차트 이미지 파일                                          │
│  - 분석 텍스트 (콘솔 출력)                                   │
│  - 투자 판단: BUY / WATCH / AVOID                            │
└─────────────────────────────────────────────────────────────┘
```

---

## 데이터 흐름

### 1️⃣ 데이터 수집 (fetch_stock_data)

```python
# 입력
ticker = "AAPL"
period = "3y"
interval = "1wk"

# Yahoo Finance API 호출
df = yf.download(ticker, period=period, interval=interval)

# 출력: DataFrame
#            Open    High     Low   Close     Volume
# Date
# 2023-01-09  130.47  133.41  129.89  130.15  70790813
# 2023-01-16  132.03  134.92  131.66  134.76  64120933
# ...
```

**처리 과정:**
1. yfinance 라이브러리가 Yahoo Finance에서 데이터 가져옴
2. 주봉이면 주 단위로, 일봉이면 일 단위로 OHLCV 데이터 반환
3. Pandas DataFrame으로 변환
4. 타임존을 UTC로 통일

### 2️⃣ 이동평균선 계산 (calculate_moving_averages)

```python
# 입력: OHLCV DataFrame
# 출력: MA 컬럼 추가된 DataFrame

# 주봉
df['MA50'] = df['Close'].rolling(window=10).mean()   # 10주 이평
df['MA200'] = df['Close'].rolling(window=40).mean()  # 40주 이평

# 일봉
df['MA50'] = df['Close'].rolling(window=50).mean()   # 50일 이평
df['MA200'] = df['Close'].rolling(window=200).mean() # 200일 이평
```

**주의사항:**
- 초기 데이터는 NaN (계산 불가)
- 10주 이평은 10주차부터 계산 가능
- 200일 이평은 200일차부터 계산 가능

### 3️⃣ 패턴 감지 (V2 모드)

```python
# pattern_detector.py의 run_pattern_detection() 함수

# 1. 각 패턴 알고리즘 실행
cup_result = detect_cup_with_handle(df)
double_bottom_result = detect_double_bottom(df)
flat_base_result = detect_flat_base(df)
htf_result = detect_high_tight_flag(df)

# 2. 품질 점수 계산 (0-100)
# - 패턴 요구사항 충족도
# - 거래량 분석
# - 이동평균선 위치

# 3. 최고 점수 패턴 선택
best_pattern = max(all_patterns, key=lambda x: x.quality)

# 4. 결과 반환
return {
    "pattern": "Cup-with-Handle",
    "quality": 100,
    "pivot_point": 69.55,
    "faults": ["NO VOLUME DRY-UP IN HANDLE"],
    "base_stage": 1,
    "volume_trend": "ACCUMULATION"
}
```

### 4️⃣ AI 분석 (Gemini Vision)

```python
# 1. 차트 이미지 로드
image = Image.open("chart.png")

# 2. 윌리엄 오닐 페르소나 프롬프트 + 이미지 전송
prompt = WILLIAM_ONEIL_ENHANCED_PERSONA + """
Analyze this chart...
"""

response = gemini_model.generate_content([prompt, image])

# 3. AI 응답 파싱
analysis = parse_ai_response(response.text)

# 4. 결과 반환
return {
    "analysis": "This stock shows...",
    "pattern_detected": "Cup with Handle",
    "action": "WATCH",
    "confidence": "HIGH"
}
```

---

## 핵심 컴포넌트

### 📦 main.py (메인 실행 파일)

**주요 함수:**

#### `fetch_stock_data(ticker, period, interval)`
- Yahoo Finance에서 데이터 다운로드
- 반환: Pandas DataFrame (OHLCV)

#### `calculate_moving_averages(df, short_window, long_window)`
- 이동평균선 계산
- 반환: MA 컬럼 추가된 DataFrame

#### `create_oneil_chart(ticker, df, interval)`
- mplfinance로 차트 생성
- 저장: chart.png

#### `main_v1(ticker)` - 기본 모드
1. 데이터 수집
2. 차트 생성
3. AI 이미지 분석
4. 결과 출력

#### `main_v2(ticker)` - 향상된 모드
1. 데이터 수집
2. **코드 기반 패턴 감지**
3. 차트 생성
4. **AI 해석 (코드 결과 기반)**
5. 결과 출력

---

### 📦 pattern_detector.py (패턴 감지 엔진)

**주요 함수:**

#### `detect_cup_with_handle(df)`
**알고리즘:**
```
1. 컵 찾기:
   - 최고점(Left Peak) 찾기
   - 최저점(Bottom) 찾기
   - 우측 최고점(Right Peak) 찾기

2. 컵 검증:
   - U자 형태인가? (V자 아님)
   - 깊이: 12-33% 하락
   - 기간: 7주 ~ 65주
   - 우측이 좌측보다 높거나 비슷

3. 핸들 찾기:
   - 컵 완성 후 작은 하락
   - 컵 상단 절반에 위치
   - 깊이: 8-12% (최대 20%)
   - 기간: 1-4주

4. 거래량 분석:
   - 컵 하락 시: 거래량 감소
   - 핸들 형성 시: 거래량 감소 (dry-up)
   - 돌파 시: 거래량 급증 (+40-50%)

5. 품질 점수 계산 (0-100)
   - 완벽한 패턴: 100점
   - 결함마다 감점
```

#### `detect_flat_base(df)`
**알고리즘:**
```
1. 횡보 구간 찾기:
   - 최소 5주 이상
   - 가격 변동폭 15% 이내

2. 검증:
   - 이전에 상승 추세 존재
   - 이동평균선 위에 위치
   - 거래량 감소
```

#### `detect_double_bottom(df)`
**알고리즘:**
```
1. W자 패턴 찾기:
   - 첫 번째 저점
   - 중간 고점
   - 두 번째 저점 (첫 번째와 비슷)

2. 검증:
   - 두 저점 차이 <4%
   - 중간 고점이 충분히 높음
   - 두 번째 저점에서 거래량 감소
```

---

### 📦 system_prompt.py (AI 페르소나)

**WILLIAM_ONEIL_ENHANCED_PERSONA:**

```python
"""
당신은 전설적인 투자자 윌리엄 오닐(William J. O'Neil)입니다.
Investor's Business Daily 창립자이자 CAN SLIM 투자 방법론의 창시자입니다.

핵심 원칙:
1. 차트 패턴 중시
2. 기관 매수 신호 (거래량)
3. 손절 철저 (7-8% 룰)
4. 시장 타이밍
5. Leading stocks 선택

당신의 목표:
- 차트를 분석하여 매수/매도 판단
- 명확한 근거 제시
- 리스크 관리 조언
"""
```

---

### 📦 feedback_manager.py (피드백 수집)

**역할:**
- AI 분석 결과에 대한 사용자 피드백 수집
- 향후 학습 데이터로 활용 예정
- 현재는 선택적 기능

---

### 📦 version.py (버전 관리)

```python
VERSION = "2.0.0"
VERSION_NAME = "Enhanced Pattern Detection"
```

---

## 분석 모드

### 🔵 V1 - Basic (AI 이미지 분석만)

**흐름:**
```
데이터 수집 → 차트 생성 → AI 분석 → 결과 출력
```

**장점:**
- 간단함
- AI가 전체적인 맥락 파악

**단점:**
- 정확도 떨어짐
- 수치가 부정확할 수 있음
- AI 할루시네이션 가능

### 🟢 V2 - Enhanced (코드 감지 + AI 해석)

**흐름:**
```
데이터 수집 → 코드 패턴 감지 → 차트 생성 → AI 해석 → 결과 출력
```

**장점:**
- 높은 정확도 (알고리즘 기반)
- 정밀한 수치 계산
- AI가 코드 결과를 검증/보완

**단점:**
- 복잡함
- 알고리즘 유지보수 필요

---

## 기술 스택

### Backend
- **Python 3.14**
- **yfinance**: Yahoo Finance API 클라이언트
- **pandas**: 데이터 분석
- **numpy**: 수치 계산
- **scipy**: Spline 보간법

### 차트 생성
- **mplfinance**: 금융 차트 전문 라이브러리
- **matplotlib**: 기본 플로팅

### AI
- **Google Gemini 2.5 Flash**: Vision + Text 분석
- **google-generativeai**: Gemini API 클라이언트

### 환경 관리
- **.env**: API 키 관리
- **python-dotenv**: 환경변수 로드

---

## 파일 구조

```
backend/services/chart_canslim_service/
├── main.py                    # 메인 실행 파일 (V1/V2 모드)
├── pattern_detector.py        # 패턴 감지 알고리즘
├── system_prompt.py           # AI 페르소나 정의
├── feedback_manager.py        # 피드백 수집
├── version.py                 # 버전 정보
├── .env                       # API 키 (gitignore)
├── .env.template              # API 키 템플릿
├── requirements.txt           # Python 패키지 목록
├── chart.png                  # 생성된 차트 (임시)
└── ARCHITECTURE.md            # 이 문서
```

---

## 실행 흐름 예시

### 코카콜라(KO) 분석 - V2 모드

```bash
$ python main.py
```

**1단계: 모드 선택**
```
Select mode (1 or 2): 2
Enter ticker symbol: KO
```

**2단계: 데이터 수집**
```
[*] Fetching 1wk data for KO (period: 3y)...
[OK] Downloaded 157 weeks of data
```

**3단계: 패턴 감지**
```
[*] Running code-based pattern detection...
  - Detecting Cup-with-Handle...
  - Detecting Double Bottom...
  - Detecting Flat Base...
  - Detecting High Tight Flag...
  [OK] Best pattern: Cup-with-Handle (quality: 100)
```

**4단계: 차트 생성**
```
[*] Creating William O'Neil style chart...
[OK] Chart saved to: chart.png
```

**5단계: AI 분석**
```
[*] V2: Analyzing with code-detected patterns + AI interpretation...
[OK] V2 Analysis complete!
```

**6단계: 결과 출력**
```
================================================================================
ANALYSIS RESULT
================================================================================

Pattern: Cup-with-Handle
Quality: 100/100
Pivot Point: $69.55
Current Price: $78.60 (+13% from pivot)

VERDICT: WATCH & WAIT

This stock is too extended from its proper buy point.
Wait for a new base to form before entering.
...
```

---

## 개선 이력

### v1.0 (초기 MVP - william_oneil_mvp.py)
- ✅ 기본 차트 생성
- ✅ AI 이미지 분석
- ❌ 패턴 오버레이 부정확
- ❌ 한글 폰트 오류

### v1.5 (중간 개선)
- ✅ 영어 텍스트로 변경
- ✅ Window Search 알고리즘 (±4주)
- ✅ Cubic Spline 보간법
- ✅ 동적 포인트 개수

### v2.0 (현재 - main.py)
- ✅ V2 Enhanced 모드
- ✅ 코드 기반 패턴 감지
- ✅ AI 해석 결합
- ✅ 일봉/주봉 자동 전환
- ✅ 동적 이평선 표시

---

## 향후 계획

### Phase 1: MVP 완성
- [ ] 모든 엣지 케이스 처리
- [ ] 데이터 기간 최적화 (5년 주봉)
- [ ] 현재 시점 중심 분석

### Phase 2: 웹 UI
- [ ] Streamlit/Flask 웹 인터페이스
- [ ] 실시간 차트 업데이트
- [ ] 여러 종목 동시 분석

### Phase 3: 고급 기능
- [ ] 포트폴리오 관리
- [ ] 알림 시스템
- [ ] 백테스팅

### Phase 4: 프로덕션
- [ ] 데이터베이스 연동
- [ ] API 서버
- [ ] 사용자 인증
- [ ] 유료화

---

## 라이선스 & 면책조항

**면책조항:**
이 도구는 교육/연구 목적으로만 사용되어야 합니다.
투자 결정은 본인의 판단과 책임 하에 이루어져야 하며,
이 도구의 분석 결과로 인한 손실에 대해 개발자는 책임지지 않습니다.

**데이터 출처:** Yahoo Finance (yfinance)
**AI 모델:** Google Gemini 2.5 Flash

---

**문서 작성일:** 2026-02-12
**버전:** 2.0.0
**작성자:** Product Engineer
