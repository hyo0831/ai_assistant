# 🚀 William O'Neil AI Investment Assistant

Google Gemini 1.5 Flash를 활용한 윌리엄 오닐 스타일 차트 분석 시스템

## 📋 개요

이 프로젝트는 전설적인 투자자 **윌리엄 오닐(William J. O'Neil)**의 CAN SLIM® 방법론을 AI로 구현한 투자 분석 도구입니다.

### 핵심 기능

1. **윌리엄 오닐 스타일 차트 생성**
   - 로그 스케일 (Log Scale)
   - 50일/200일 이동평균선
   - 거래량 분석 (Volume Analysis)

2. **AI 차트 분석**
   - CAN SLIM 원칙 기반 분석
   - 차트 패턴 인식 (Cup with Handle, Double Bottom 등)
   - 명확한 매수/관망/매도 시그널

## 🛠️ 설치 방법

### 1. 필수 라이브러리 설치

```bash
pip install -r requirements.txt
```

또는 직접 설치:

```bash
pip install yfinance mplfinance google-generativeai pandas pillow
```

### 2. Gemini API Key 설정

Google AI Studio에서 API 키를 발급받으세요:
👉 https://aistudio.google.com/app/apikey

#### 방법 A: 환경변수 설정 (권장)

**Windows (PowerShell):**
```powershell
$env:GEMINI_API_KEY="your-api-key-here"
```

**Windows (CMD):**
```cmd
set GEMINI_API_KEY=your-api-key-here
```

**Mac/Linux:**
```bash
export GEMINI_API_KEY="your-api-key-here"
```

#### 방법 B: 코드에 직접 입력

[main.py](main.py)의 17번째 줄을 수정:

```python
GEMINI_API_KEY = "your-api-key-here"
```

## 🚀 사용 방법

### 기본 사용

[main.py](main.py)의 마지막 부분에서 티커를 수정:

```python
TICKER = "AAPL"  # 분석하고 싶은 종목 코드 입력
```

실행:

```bash
python main.py
```

### 종목 코드 예시

**미국 주식:**
- Apple: `AAPL`
- Tesla: `TSLA`
- Microsoft: `MSFT`
- NVIDIA: `NVDA`
- Google: `GOOGL`

**한국 주식:**
- 삼성전자: `005930.KS`
- SK하이닉스: `000660.KS`
- NAVER: `035420.KS`
- 카카오: `035720.KS`

## 📊 출력 결과

### 1. 차트 이미지
`chart.png` 파일로 저장됩니다.

### 2. AI 분석 리포트
터미널에 다음 내용이 출력됩니다:
- Trend Status (추세 상태)
- Pattern Recognition (패턴 인식)
- Volume Behavior (거래량 분석)
- Buy Point & Entry (매수 시점)
- Risk Management (리스크 관리)
- Final Verdict (최종 판단)

## 🎯 윌리엄 오닐의 CAN SLIM® 원칙

| 요소 | 의미 |
|------|------|
| **C** | Current Quarterly Earnings (최근 분기 실적) |
| **A** | Annual Earnings Growth (연간 실적 성장률) |
| **N** | New Products, New Management, New Highs (신제품, 신경영진, 신고가) |
| **S** | Supply and Demand (수급: 주식 수와 거래량) |
| **L** | Leader or Laggard (업종 선도주 vs 후발주) |
| **I** | Institutional Sponsorship (기관 투자자 지원) |
| **M** | Market Direction (시장 방향성) |

## 🔧 고급 설정

### 차트 기간 변경

[main.py](main.py)의 `fetch_stock_data` 함수 호출 시:

```python
df = fetch_stock_data(ticker, period="12mo")  # 12개월
df = fetch_stock_data(ticker, period="2y")    # 2년
```

### 차트 스타일 커스터마이징

[main.py](main.py)의 `create_oneil_chart` 함수에서 수정 가능:
- 이동평균선 색상/두께
- 차트 크기 (figsize)
- 해상도 (dpi)

## ⚠️ 주의사항

1. **투자 결정의 참고 자료일 뿐입니다**
   - AI 분석은 보조 도구이며, 최종 투자 결정은 본인의 책임입니다.

2. **API 사용량 제한**
   - Gemini API 무료 티어는 분당 요청 수 제한이 있습니다.

3. **데이터 정확성**
   - yfinance는 비공식 API이므로 가끔 데이터 오류가 있을 수 있습니다.

## 📚 참고 자료

- [How to Make Money in Stocks](https://www.investors.com/how-to-invest/how-to-make-money-in-stocks/) - William O'Neil's Book
- [Investor's Business Daily](https://www.investors.com/)
- [CAN SLIM Methodology](https://www.investors.com/ibd-university/can-slim/)

## 📄 라이선스

이 프로젝트는 교육 및 개인 투자 연구 목적으로 제작되었습니다.

---

**Made with ❤️ by Claude Code**
