# William O'Neil AI Investment Assistant - Mac

## Quick Start

```bash
cd /Users/hyo/Desktop/ai_assistant/hyochang
source venv/bin/activate
export GEMINI_API_KEY='your-api-key-here'
python3 main.py
```

---

## Setup

### 1. Python 확인
```bash
python3 --version  # 3.14+ 필요
```

### 2. 가상환경 활성화
```bash
source venv/bin/activate
```

### 3. 패키지 설치
```bash
pip install -r requirements.txt
```

### 4. API 키 설정

**임시 (현재 세션만):**
```bash
export GEMINI_API_KEY='your-key'
```

**영구 설정:**
```bash
echo 'export GEMINI_API_KEY="your-key"' >> ~/.zshrc
source ~/.zshrc
```

API 키 발급: [Google AI Studio](https://aistudio.google.com/app/apikey)

---

## 실행

```bash
python3 main.py
```

실행하면 모드와 티커를 선택합니다:

```
================================================================================
  WILLIAM O'NEIL AI INVESTMENT ASSISTANT  v2.0.0
================================================================================

  [1] V1 - Basic (AI image analysis only)
  [2] V2 - Enhanced (Code pattern detection + AI interpretation)

================================================================================
  Select mode (1 or 2): 2
  Enter ticker symbol (e.g., AAPL): AMD
```

### V1 vs V2

| | V1 - Basic | V2 - Enhanced |
|---|---|---|
| 방식 | AI가 차트 이미지만 보고 분석 | 코드가 패턴 감지 후 AI가 해석 |
| 정확도 | 이미지 인식 의존 | 수치 기반 + AI 해석 |
| 패턴 감지 | AI 주관적 판단 | 코드 자동 감지 (품질 점수 포함) |
| 거래량 분석 | 시각적 판단 | 축적/분배일 자동 카운팅 |
| 용도 | 빠른 분석 | 정확한 분석 |

### 종목 예시
```
미국: AAPL, NVDA, TSLA, MSFT, AMD, GOOGL
한국: 005930.KS (삼성전자), 000660.KS (SK하이닉스)
```

---

## 프로젝트 구조

```
hyochang/
  main.py              # 메인 프로그램 (V1/V2 모드 선택)
  system_prompt.py     # William O'Neil CAN SLIM 시스템 프롬프트
  pattern_detector.py  # V2 코드 기반 패턴 감지 엔진
  feedback_manager.py  # 자동 학습 피드백 시스템
  version.py           # 버전 관리
  requirements.txt     # Python 패키지 목록
  .env.template        # API 키 템플릿
  setup_mac.sh         # Mac 자동 설정 스크립트
  feedback/            # 사용자 피드백 저장 (git 미추적)
```

---

## V2 패턴 감지 엔진

V2 모드에서 자동 감지하는 패턴:

| 패턴 | 설명 | 오닐 기준 |
|---|---|---|
| Cup-with-Handle | U자형 컵 + 핸들 | 7-65주, 깊이 12-33% |
| Double Bottom | W자형 이중 바닥 | 두 번째 바닥 undercut |
| Flat Base | 횡보 후 돌파 | 5주+, 조정 10-15% |
| High Tight Flag | 급등 후 깃발 | 100%+ 상승 후 10-25% 조정 |

추가 분석:
- 거래량 분석 (축적일/분배일/급증/건조)
- Base Stage 카운팅 (1-4단계)
- 패턴 품질 점수 (0-100)
- 불량 패턴 필터링

---

## Troubleshooting

| 에러 | 해결 |
|---|---|
| `GEMINI_API_KEY is not set` | `export GEMINI_API_KEY='your-key'` |
| `No module named 'xxx'` | `source venv/bin/activate && pip install -r requirements.txt` |
| `No data found for ticker` | 티커 확인 (한국: `.KS` 접미사 필요) |

---

## 출력 파일

- `chart.png` - 주봉 차트 (10주/40주 이동평균선)

---

## 보안

API 키를 Git에 커밋하지 마세요. `.gitignore`에 `.env` 포함되어 있습니다.
