# 윌리엄 오닐 AI 투자 어시스턴트 (William O'Neil AI Investment Assistant)

## 📌 프로젝트 개요

**Google Gemini API를 활용하여 주식 차트를 윌리엄 오닐(William J. O'Neil)의 CAN SLIM 방법론으로 자동 분석하고, 매수/관망/회피 판단을 제공하는 AI 기반 투자 분석 시스템**

---

## 📂 디렉토리 구조 (Tree View)

```
hyochang/
│
├── main.py                  # 🎯 핵심 실행 파일 - 차트 생성 및 AI 분석
│   ├── STEP 1: 차트 생성기 (The Eye)
│   │   ├── fetch_stock_data()           # yfinance로 주가 데이터 다운로드
│   │   ├── calculate_moving_averages()  # 10주/40주 이동평균 계산
│   │   └── create_oneil_chart()         # 로그스케일 차트 생성 (mplfinance)
│   │
│   ├── STEP 2: 페르소나 프롬프트 (The Brain)
│   │   └── WILLIAM_ONEIL_PERSONA        # CAN SLIM 분석 지침 (750+ 라인)
│   │
│   └── STEP 3: AI 분석 실행 (Execution)
│       ├── analyze_chart_with_gemini()  # Gemini Vision API 호출
│       ├── parse_pattern_data()         # JSON 패턴 데이터 추출
│       └── create_annotated_chart()     # 패턴 시각화 차트 생성
│
├── quick_test.py            # ✅ 사전 검증 스크립트 - 라이브러리 & API 키 체크
│   ├── check_imports()      # yfinance, mplfinance 등 설치 확인
│   ├── check_api_key()      # GEMINI_API_KEY 환경변수 확인
│   ├── test_yfinance()      # Yahoo Finance 연결 테스트
│   └── test_gemini_api()    # Gemini API 연결 테스트
│
├── list_models.py           # 📋 유틸리티 - 사용 가능한 Gemini 모델 목록 조회
│
├── chart.png                # 📊 생성된 기본 차트 (로그스케일 + 이동평균)
└── chart_annotated.png      # 📊 AI 분석 결과가 표시된 패턴 차트
```

---

## 🔄 핵심 로직 흐름 (Data Flow)

### 전체 파이프라인

```
[입력] 종목 코드 (Ticker)
   ↓
[처리 1] 데이터 수집 (yfinance)
   │     - 3년치 주봉 데이터 다운로드
   │     - OHLCV (시가/고가/저가/종가/거래량) 추출
   ↓
[처리 2] 지표 계산 (pandas)
   │     - 10주 이동평균 (MA10)
   │     - 40주 이동평균 (MA40)
   ↓
[처리 3] 차트 생성 (mplfinance)
   │     - 로그 스케일 캔들차트
   │     - 이동평균선 오버레이
   │     - 거래량 바 차트
   │     → chart.png 저장
   ↓
[처리 4] AI 비전 분석 (google.generativeai)
   │     - Gemini 2.5 Flash 모델 사용
   │     - 윌리엄 오닐 페르소나 프롬프트 주입
   │     - 차트 이미지 + 프롬프트 전송
   ↓
[처리 5] 결과 파싱 (re, json)
   │     - JSON 패턴 데이터 추출
   │     - 매수 포인트, 지지/저항선 추출
   ↓
[처리 6] 패턴 시각화 (matplotlib)
   │     - Cup with Handle, Double Bottom 등 패턴 표시
   │     - 매수/손절 라인 추가
   │     → chart_annotated.png 저장
   ↓
[출력] 분석 리포트 + 시각화 차트
   - BUY NOW / WATCH & WAIT / AVOID 판단
   - 구체적인 가격 레벨 (Buy Point, Stop Loss)
```

### 각 단계별 사용 라이브러리

| 단계 | 기능 | 라이브러리 | 핵심 이유 |
|------|------|-----------|----------|
| 1️⃣ 데이터 수집 | Yahoo Finance에서 주가 데이터 다운로드 | `yfinance` | 무료 & 한국/미국 주식 모두 지원 |
| 2️⃣ 지표 계산 | 이동평균선 계산 | `pandas` | 시계열 데이터 처리에 최적화 |
| 3️⃣ 차트 생성 | 캔들스틱 차트 렌더링 | `mplfinance` | 금융 차트 전문 라이브러리 |
| 4️⃣ AI 분석 | 이미지 기반 차트 분석 | `google.generativeai` | Gemini의 Vision 능력 활용 |
| 5️⃣ 데이터 파싱 | JSON 추출 및 정규표현식 | `re`, `json` | AI 출력에서 구조화 데이터 추출 |
| 6️⃣ 패턴 시각화 | 차트에 패턴 오버레이 | `matplotlib` | 저수준 그래픽 제어 |

---

## 🔍 함수별 상세 설명

### 📥 STEP 1: 데이터 수집 및 차트 생성

#### `fetch_stock_data(ticker, period="3y", interval="1wk")`
**역할:** Yahoo Finance API를 통해 주가 데이터 다운로드

**파라미터:**
- `ticker`: 종목 코드 (예: `"AAPL"`, `"005930.KS"` 삼성전자)
- `period`: 데이터 기간 (기본 3년)
- `interval`: 데이터 간격 (기본 `"1wk"` 주봉, `"1d"` 일봉 가능)

**반환값:** pandas DataFrame (OHLCV 데이터)

**팀원 참고:**
- 한국 주식은 `.KS` 접미사 필요 (예: `"005930.KS"`)
- 데이터가 없으면 `ValueError` 예외 발생

---

#### `calculate_moving_averages(df, short_window=10, long_window=40)`
**역할:** 이동평균선 계산 (윌리엄 오닐의 핵심 지표)

**왜 10주/40주인가?**
- **10주 이동평균**: 단기 추세 파악 (일봉의 50일 이평에 해당)
- **40주 이동평균**: 장기 추세 및 강세장 확인 (일봉의 200일 이평에 해당)
- 윌리엄 오닐의 연구: 강세주는 10주선 위에서 거래됨

**파라미터:**
- `short_window`: 단기 이동평균 기간 (주봉: 10, 일봉: 50)
- `long_window`: 장기 이동평균 기간 (주봉: 40, 일봉: 200)

---

#### `create_oneil_chart(ticker, df, output_path="chart.png", interval="1wk")`
**역할:** 윌리엄 오닐 스타일의 주봉 차트 생성

**핵심 설정 및 이유:**

1. **로그 스케일 (`yscale='log'`)** - [main.py:138](main.py#L138)
   - **왜 사용?** 백분율 변화를 시각화하기 위함
   - 예시: $10 → $20 (100% 상승)과 $100 → $200 (100% 상승)이 같은 높이로 표시됨
   - 윌리엄 오닐: "주식은 퍼센트로 움직인다"

2. **Yahoo 스타일 (`base_mpf_style='yahoo'`)** - [main.py:115](main.py#L115)
   - 깔끔하고 전문적인 차트 스타일
   - 상승 캔들 = 녹색, 하락 캔들 = 빨강

3. **거래량 패널 (`volume=True`)** - [main.py:135](main.py#L135)
   - 거래량은 매수 타이밍 판단의 핵심
   - 돌파 시 거래량 급증 = 기관 매수 신호

**출력:** `chart.png` 파일 저장 (해상도 150 DPI)

---

### 🧠 STEP 2: AI 페르소나 시스템 프롬프트

#### `WILLIAM_ONEIL_PERSONA` - [main.py:157-215](main.py#L157-L215)
**역할:** Gemini AI에게 윌리엄 오닐의 사고방식을 주입하는 750줄 분량의 상세 프롬프트

**구조:**
1. **페르소나 설정**: "당신은 Investor's Business Daily 창립자 윌리엄 오닐입니다"
2. **분석 프레임워크 (CAN SLIM)**:
   - Trend Analysis (추세 분석)
   - Chart Pattern Recognition (패턴 인식)
   - Volume Analysis (거래량 분석)
   - Buy Point Identification (매수 포인트)
   - Risk Assessment (리스크 관리)
3. **커뮤니케이션 스타일**: 자신감 있고 단호한 판단

**핵심 패턴:**
- **Cup with Handle** (컵 앤 핸들): 7-65주 형성, 핸들 1-5주
- **Double Bottom** (W자형): 두 번째 저점에서 거래량 감소
- **Flat Base** (평평한 베이스): 5주 이상 15% 이내 횡보

---

### 🤖 STEP 3: AI 분석 실행

#### `analyze_chart_with_gemini(image_path, ticker)`
**역할:** Gemini 2.5 Flash 모델에 차트 이미지 전송 및 분석 수행

**핵심 로직:**
1. [main.py:239-242](main.py#L239-L242): `system_instruction`으로 윌리엄 오닐 페르소나 주입
2. [main.py:245](main.py#L245): PIL을 사용해 차트 이미지 로드
3. [main.py:248-305](main.py#L248-L305): 분석 프롬프트 작성
   - PART 1: JSON 형식 패턴 데이터 요청
   - PART 2: 마크다운 형식 상세 분석
4. [main.py:308](main.py#L308): `model.generate_content([프롬프트, 이미지])` 멀티모달 요청

**반환값:** AI 분석 텍스트 (JSON + Markdown)

**주의사항:**
- Windows 콘솔 호환성을 위해 이모지 제거 ([main.py:313](main.py#L313))

---

#### `parse_pattern_data(analysis_text)`
**역할:** AI 응답에서 JSON 패턴 데이터 추출

**파싱 로직:**
1. 정규표현식으로 `\`\`\`json ... \`\`\`` 블록 찾기
2. JSON 파싱하여 딕셔너리 변환
3. 실패 시 `None` 반환

**추출 데이터:**
```json
{
  "pattern_type": "Cup with Handle",
  "key_levels": {
    "buy_point": 195.5,
    "stop_loss": 180.2,
    "support": 175.0,
    "resistance": 190.0
  },
  "pattern_points": {
    "left_peak_week": 110,
    "bottom_week": 125,
    "right_peak_week": 140,
    "handle_end_week": 148
  },
  "verdict": "BUY NOW"
}
```

---

#### `create_annotated_chart(ticker, df, pattern_data, output_path="chart_annotated.png")`
**역할:** AI가 식별한 패턴을 차트에 시각적으로 표시

**시각화 요소:**
1. **수평선** ([main.py:440-448](main.py#L440-L448))
   - 매수 포인트 (녹색 점선)
   - 손절 라인 (빨간 점선)
   - 지지선/저항선 (주황/보라 점선)

2. **패턴 라인** ([main.py:461-531](main.py#L461-L531))
   - Cup with Handle: ① 왼쪽 정점 → ② 컵 바닥 → ③ 오른쪽 정점 → ④ 핸들 끝
   - 각 단계에 번호 마커 및 라벨 표시

3. **타이틀 정보** ([main.py:414-415](main.py#L414-L415))
   - 패턴 타입 및 최종 판단 (BUY NOW / WATCH & WAIT / AVOID)

---

## 👥 팀원별 참고 사항

### 🎨 M2 (Data Engineer) - 차트 스타일 수정

**Q: 차트 색상, 폰트, 레이아웃을 변경하려면?**

#### 📍 위치: [main.py:114-125](main.py#L114-L125)

```python
style = mpf.make_mpf_style(
    base_mpf_style='yahoo',  # ← 스타일 변경 ('yahoo', 'charles', 'sas', 'nightclouds')
    rc={
        'font.size': 10,           # ← 전체 폰트 크기
        'axes.labelsize': 12,      # ← 축 레이블 크기
        'axes.titlesize': 14,      # ← 제목 크기
        'xtick.labelsize': 10,     # ← X축 틱 레이블
        'ytick.labelsize': 10,     # ← Y축 틱 레이블
        'figure.facecolor': 'white',  # ← 배경색
        'axes.facecolor': 'white'     # ← 차트 영역 배경색
    }
)
```

**차트 크기 변경:** [main.py:137](main.py#L137)
```python
figsize=(16, 10)  # ← (가로, 세로) 인치 단위
```

**이동평균선 색상:** [main.py:109-110](main.py#L109-L110)
```python
mpf.make_addplot(df['MA50'], color='blue', width=1.5),   # ← 10주선 색상
mpf.make_addplot(df['MA200'], color='red', width=1.5)    # ← 40주선 색상
```

**로그 스케일 끄기:** [main.py:138](main.py#L138)
```python
yscale='log'  # ← 'linear'로 변경하면 선형 스케일
```

---

### 🤖 M1 (AI Engineer) - AI 프롬프트 수정

**Q: AI 분석 기준을 변경하려면?**

#### 📍 위치: [main.py:157-215](main.py#L157-L215) - `WILLIAM_ONEIL_PERSONA` 변수

**분석 프레임워크 수정 예시:**

1. **거래량 임계값 변경:**
   ```python
   # 현재: "40-50% above average weekly volume"
   # 변경 예시: "30-40% above average" (기준 완화)
   ```
   위치: [main.py:183](main.py#L183)

2. **손절 기준 수정:**
   ```python
   # 현재: "Usually 7-8% below buy point"
   # 변경 예시: "5-6% below buy point" (더 타이트한 손절)
   ```
   위치: [main.py:194](main.py#L194)

3. **패턴 인식 추가:**
   [main.py:174-180](main.py#L174-L180)에 새로운 패턴 정의 추가
   ```python
   - **Triple Bottom**: 세 번의 저점 테스트 후 상승
   ```

**AI 모델 변경:**
[main.py:240](main.py#L240)
```python
model_name='gemini-2.5-flash'  # ← 'gemini-1.5-pro'로 변경 (더 정확하지만 느림)
```

**프롬프트 출력 형식 수정:**
[main.py:248-305](main.py#L248-L305) - `analysis_prompt` 변수 전체

---

### 💻 M3 (Backend) - 시스템 통합

**API 키 관리:**
- 환경변수: `GEMINI_API_KEY` ([main.py:26](main.py#L26))
- 발급처: https://aistudio.google.com/app/apikey

**파일 저장 경로 변경:**
```python
CHART_OUTPUT_PATH = "chart.png"  # ← [main.py:29](main.py#L29)
# 변경 예시: f"charts/{ticker}_{datetime.now():%Y%m%d}.png"
```

**종목 코드 입력:**
[main.py:664](main.py#L664)
```python
TICKER = "AAPL"  # ← 여기에 종목 코드 입력
```

**배치 분석 (여러 종목 동시 분석):**
```python
for ticker in ["AAPL", "TSLA", "NVDA"]:
    main(ticker)
```

---

### 🎯 M4 (Frontend / PM) - 사용자 워크플로우

**실행 순서:**

1. **사전 검증 (필수):**
   ```bash
   python quick_test.py
   ```
   - 라이브러리 설치 확인
   - API 키 유효성 검사
   - yfinance, Gemini API 연결 테스트

2. **메인 분석 실행:**
   ```bash
   python main.py
   ```

3. **출력 파일 확인:**
   - `chart.png`: 기본 차트
   - `chart_annotated.png`: 패턴 분석 차트

**에러 핸들링:**
- 종목 코드 오류 → `ValueError: No data found for ticker`
- API 키 누락 → Gemini API 인증 실패
- 라이브러리 누락 → `ImportError`

---

## 🚀 빠른 시작 (Quick Start)

### 1. 저장소 클론
```bash
git clone <your-repository-url>
cd hyochang
```

### 2. 가상환경 생성 (권장)
```bash
# Python 가상환경 생성
python -m venv venv

# 가상환경 활성화
# Windows
venv\Scripts\activate
# Mac/Linux
source venv/bin/activate
```

### 3. 패키지 설치
```bash
pip install -r requirements.txt
```

### 4. API 키 설정
```bash
# .env.example을 복사하여 .env 파일 생성
cp .env.example .env

# .env 파일을 열어서 실제 API 키 입력
# GEMINI_API_KEY=your-actual-api-key-here
```

**API 키 발급:**
1. https://aistudio.google.com/app/apikey 방문
2. "Create API Key" 클릭
3. 생성된 키를 복사하여 `.env` 파일에 붙여넣기

### 5. 실행
```bash
python main.py
```

---

## 🛠️ 상세 설치 가이드

### 필수 라이브러리 설치
```bash
pip install yfinance mplfinance google-generativeai pandas pillow matplotlib
```

### API 키 설정
```bash
# Windows (PowerShell)
$env:GEMINI_API_KEY = "your-api-key-here"

# Mac/Linux
export GEMINI_API_KEY="your-api-key-here"
```

### 실행
```bash
# 1단계: 환경 검증
python quick_test.py

# 2단계: 차트 분석 실행
python main.py
```

---

## 📊 사용 예시

### 미국 주식 분석
```python
TICKER = "NVDA"  # 엔비디아
main(TICKER)
```

### 한국 주식 분석
```python
TICKER = "005930.KS"  # 삼성전자
main(TICKER)
```

### 일봉 차트로 변경
[main.py:612-616](main.py#L612-L616)에서:
```python
interval = "1d"  # "1wk" → "1d"로 변경
df = fetch_stock_data(ticker, period="1y", interval=interval)
df = calculate_moving_averages(df, short_window=50, long_window=200)  # 50일/200일 이평
```

---

## 🎓 참고 자료

- **윌리엄 오닐 투자법:** 『How to Make Money in Stocks』
- **CAN SLIM 방법론:** https://www.investors.com/ibd-university/can-slim/
- **Gemini API 문서:** https://ai.google.dev/docs
- **yfinance 문서:** https://pypi.org/project/yfinance/

---

## 📝 라이센스 및 면책

이 프로젝트는 교육 목적으로 작성되었습니다.
투자 판단은 본인 책임이며, AI 분석 결과는 참고용입니다.

---

## ⚠️ GitHub 업로드 시 주의사항

### 절대 커밋하면 안 되는 파일:
- `.env` (실제 API 키 포함)
- `chart.png`, `chart_annotated.png` (생성된 차트 파일)
- `__pycache__/` (Python 캐시)

### 안전하게 GitHub에 올리기:
```bash
# 1. .gitignore가 제대로 설정되었는지 확인
cat .gitignore

# 2. git 상태 확인 (민감한 파일이 포함되지 않았는지 체크)
git status

# 3. 안전한 파일만 커밋
git add .
git commit -m "Initial commit: William O'Neil AI Investment Assistant"

# 4. GitHub에 푸시
git push origin main
```

### 실수로 API 키를 커밋한 경우:
1. **즉시 API 키를 재발급** (https://aistudio.google.com/app/apikey)
2. Git 히스토리에서 제거:
   ```bash
   git filter-branch --force --index-filter \
     "git rm --cached --ignore-unmatch .env" \
     --prune-empty --tag-name-filter cat -- --all
   ```
3. 강제 푸시 (주의!):
   ```bash
   git push origin --force --all
   ```

---

**Created by:** hyochang team
**Last Updated:** 2026-02-05
**License:** MIT (Educational Purpose)
