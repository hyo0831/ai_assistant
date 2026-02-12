# Mac에서 실행하기 🍎

## 📋 사전 준비사항

### 1. Python 설치 확인
```bash
python3 --version
```
Python 3.14.2 이상이 설치되어 있어야 합니다.

만약 설치되지 않았다면:
```bash
brew install python3
```

---

## 🚀 빠른 시작 (Quick Start)

### 1단계: 가상환경 활성화
```bash
cd /Users/hyo/Desktop/ai_assistant/hyochang
source venv/bin/activate
```

프롬프트 앞에 `(venv)`가 표시되면 성공입니다.

### 2단계: Gemini API 키 설정

#### 방법 A: 임시 설정 (현재 터미널 세션에만 적용)
```bash
export GEMINI_API_KEY='your-api-key-here'
```

#### 방법 B: 영구 설정 (권장)
1. API 키를 쉘 설정 파일에 추가:
```bash
echo 'export GEMINI_API_KEY="your-api-key-here"' >> ~/.zshrc
source ~/.zshrc
```

2. 설정 확인:
```bash
echo $GEMINI_API_KEY
```

**API 키 발급 방법:**
1. [Google AI Studio](https://aistudio.google.com/app/apikey) 접속
2. "Create API Key" 클릭
3. 생성된 키 복사

### 3단계: 프로그램 실행
```bash
python3 main.py
```

---

## 🔧 상세 설정 가이드

### 의존성 재설치가 필요한 경우
```bash
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 설치된 패키지 확인
```bash
pip list
```

### 환경 테스트
quick_test.py를 실행하여 모든 설정이 올바른지 확인:
```bash
python3 quick_test.py
```

---

## 📝 프로그램 실행 예시

### 미국 주식 분석 (Apple)
[main.py:671](main.py#L671) 수정:
```python
TICKER = "AAPL"  # Apple Inc.
main(TICKER)
```

실행:
```bash
python3 main.py
```

### 한국 주식 분석 (삼성전자)
[main.py:671](main.py#L671) 수정:
```python
TICKER = "005930.KS"  # 삼성전자
main(TICKER)
```

실행:
```bash
python3 main.py
```

### 다른 종목 예시
```python
# 미국 주식
"NVDA"    # 엔비디아
"TSLA"    # 테슬라
"MSFT"    # 마이크로소프트
"GOOGL"   # 구글

# 한국 주식
"005930.KS"  # 삼성전자
"000660.KS"  # SK하이닉스
"035420.KS"  # NAVER
```

---

## 🐛 문제 해결 (Troubleshooting)

### 문제 1: "GEMINI_API_KEY is not set" 에러
**해결책:**
```bash
export GEMINI_API_KEY='your-api-key-here'
```
또는 영구 설정:
```bash
echo 'export GEMINI_API_KEY="your-api-key-here"' >> ~/.zshrc
source ~/.zshrc
```

### 문제 2: "No module named 'xxx'" 에러
**해결책:**
```bash
source venv/bin/activate  # 가상환경 활성화 확인
pip install -r requirements.txt
```

### 문제 3: "No data found for ticker" 에러
**원인:** 잘못된 티커 심볼
**해결책:**
- 미국 주식: 티커만 입력 (예: "AAPL")
- 한국 주식: `.KS` 접미사 필요 (예: "005930.KS")

### 문제 4: matplotlib 차트가 표시되지 않음
**해결책:**
차트는 PNG 파일로 저장됩니다:
- `chart.png` - 기본 차트
- `chart_annotated.png` - AI 분석이 표시된 차트

Finder로 파일을 열거나:
```bash
open chart_annotated.png
```

---

## 📊 출력 파일

프로그램 실행 후 생성되는 파일:
1. **chart.png** - 기본 윌리엄 오닐 스타일 차트
2. **chart_annotated.png** - AI 패턴 분석이 표시된 차트

---

## 💡 유용한 팁

### 가상환경 비활성화
```bash
deactivate
```

### 여러 종목 연속 분석
[main.py](main.py)의 `main()` 함수를 수정:
```python
if __name__ == "__main__":
    tickers = ["AAPL", "NVDA", "TSLA", "GOOGL"]
    for ticker in tickers:
        print(f"\n{'='*80}")
        print(f"분석 시작: {ticker}")
        print(f"{'='*80}\n")
        main(ticker)
```

### 차트 저장 경로 변경
[main.py:36](main.py#L36):
```python
CHART_OUTPUT_PATH = "/Users/hyo/Desktop/charts/chart.png"
```

---

## 📚 추가 자료

- [Google Gemini API 문서](https://ai.google.dev/docs)
- [yfinance 문서](https://pypi.org/project/yfinance/)
- [윌리엄 오닐 CAN SLIM](https://www.investors.com/ibd-university/can-slim/)

---

## 🔒 보안 주의사항

⚠️ **중요:** API 키를 Git에 커밋하지 마세요!

`.gitignore`에 다음 추가:
```
.env
.env.local
```

---

## ✅ 체크리스트

실행 전 확인사항:
- [ ] Python 3.14+ 설치 확인
- [ ] 가상환경 활성화 (`source venv/bin/activate`)
- [ ] Gemini API 키 설정 (`export GEMINI_API_KEY='...'`)
- [ ] 의존성 패키지 설치 완료 (`pip list` 확인)
- [ ] 인터넷 연결 확인 (Yahoo Finance, Gemini API 접근 필요)

모든 항목이 체크되었다면:
```bash
python3 main.py
```

Good luck! 🚀📈
