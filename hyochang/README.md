# 윌리엄 오닐 AI 투자 어시스턴트 (William O'Neil AI Investment Assistant)

> **Version 2.1.0** | Google Gemini + CAN SLIM 방법론 기반 주식 분석 시스템

---

## 📌 프로젝트 개요

**Google Gemini API를 활용하여 주식 차트를 윌리엄 오닐(William J. O'Neil)의 CAN SLIM 방법론으로 자동 분석하고, 매수/관망/회피 판단을 제공하는 AI 기반 투자 분석 시스템**

- 기술적 분석 (차트 패턴, 이동평균, RS Rating)과 기본적 분석 (CAN SLIM 펀더멘털)을 통합
- AI가 O'Neil의 원문 규칙을 참조(RAG)하여 한국어로 종합 판단
- 미국 및 한국(KS/KQ) 주식 모두 지원

---

## 📂 디렉토리 구조

```
hyochang/
│
├── main.py                      # 메인 실행 파일 - 차트 생성 및 AI 분석
├── pattern_detector.py          # 코드 기반 패턴 감지 엔진
├── fundamental_analyzer.py      # CAN SLIM 펀더멘털 분석 오케스트레이터
├── feedback_manager.py          # AI 분석 피드백 저장 관리
├── version.py                   # 버전 정보 및 CHANGELOG
├── requirements.txt             # 의존성 패키지 목록
├── quick_test.py                # 사전 환경 검증 스크립트
├── list_models.py               # 사용 가능한 Gemini 모델 목록 조회
│
├── canslim/                     # CAN SLIM 요소별 모듈
│   ├── __init__.py
│   ├── c_current_earnings.py    # C: 최근 분기 실적 (5개 분기 YoY 성장률)
│   ├── a_annual_earnings.py     # A: 연간 실적 (5개년 추이, ROE, P/E)
│   ├── n_new_catalyst.py        # N: 신제품/촉매 (Gemini AI 조사)
│   ├── s_supply_demand.py       # S: 수급 (시가총액, 부채, 자사주)
│   ├── l_leader_laggard.py      # L: 리더/래거드 (RS Rating)
│   ├── i_institutional.py       # I: 기관 보유 현황
│   └── m_market_direction.py    # M: 시장 방향 (Distribution Day)
│
├── prompt/                      # AI 시스템 프롬프트 (자동 생성)
├── feedback/                    # 분석 피드백 저장 디렉토리
└── chart.png                    # 생성된 분석 차트
```

---

## 🔄 분석 모드

### [1] V1 - Basic
AI가 차트 이미지를 직접 보고 시각적으로 분석합니다.

### [2] V2 - Enhanced (권장)
코드가 패턴을 먼저 감지하고, 펀더멘털 분석 후 AI가 종합 해석합니다.

```
[입력] 종목 코드 (Ticker)
   ↓
[패턴 감지] pattern_detector.py
   │     - Cup-with-Handle / Double Bottom / Flat Base / High Tight Flag
   │     - RS Rating 계산 (미국: S&P500, 한국KS: KOSPI, 한국KQ: KOSDAQ)
   │     - Volume Accumulation/Distribution 분석
   │     - Base Stage 카운팅
   ↓
[펀더멘털 분석] canslim/ 모듈들
   │     - C: 5개 분기 YoY EPS 성장률 + 가속/감속 판단
   │     - A: 5개년 연간 순이익 추이, ROE, P/E
   │     - N: Gemini AI로 신제품/신경영진/촉매 조사
   │     - S: 시가총액, 유통주식수, 부채비율, 자사주매입
   │     - L: RS Rating, 섹터/산업군
   │     - I: 기관 보유율 및 주요 기관 목록
   │     - M: S&P500/NASDAQ Distribution Day, 추세
   ↓
[차트 생성] mplfinance
   │     - 로그스케일 캔들차트 + 이동평균선
   │     - 패턴 감지 결과 오버레이
   ↓
[AI 종합 분석] Gemini
   │     - 패턴 데이터 + 펀더멘털 데이터 + O'Neil 원문 규칙 통합
   │     - 한국어로 CAN SLIM 8개 섹션 분석 출력
   ↓
[출력] 한국어 투자 판단 리포트
   - BUY / WATCH & WAIT / AVOID 결론
   - RS Rating, 패턴 품질, 구체적 가격 레벨
```

### [3] Compare - 다중 종목 비교
여러 종목을 입력하면 RS Rating, 패턴, 펀더멘털 핵심 지표를 테이블로 비교합니다.

---

## 🔑 CAN SLIM 방법론

| 요소 | 의미 | O'Neil 기준 |
|------|------|------------|
| **C** | Current Quarterly Earnings | 최근 분기 EPS YoY 25-50%+ 성장 (이상적: 40-500%+) |
| **A** | Annual Earnings | 최근 3-5년 연속 25%+ 연간 성장, ROE 17%+ |
| **N** | New Products/Management/Highs | 혁신적 신제품, 새 경영진, 신고가 돌파 |
| **S** | Supply & Demand | 소형주 선호, 낮은 부채, 자사주매입은 긍정 신호 |
| **L** | Leader or Laggard | RS Rating 85+ (시장 선도주), 산업군 상위 1-2위 |
| **I** | Institutional Sponsorship | 우수 기관투자자 보유, 과다보유는 위험 신호 |
| **M** | Market Direction | 시장 방향이 투자의 50%; Distribution Day 5개+ = 정점 신호 |

---

## 🔍 핵심 기능 상세

### RS Rating (Relative Strength)
- 종목 코드 접미사에 따라 자동으로 벤치마크 선택
  - `.KS` → KOSPI (`^KS11`)
  - `.KQ` → KOSDAQ (`^KQ11`)
  - `.T` → Nikkei (`^N225`)
  - 기본 → S&P 500 (`^GSPC`)
- 1~99 점수: 99 = 시장 상위 1%

### Distribution Day (분산일)
- 정의: 지수가 전일 대비 -0.2% 이상 하락 + 전일보다 높은 거래량
- 의미: 기관들이 대량 매도하는 날 → "큰손들이 빠져나가는 발자국"
- 4~5주 내 5개 이상 → O'Neil 시장 정점(Market Top) 경고

### 패턴 감지 엔진
- **Cup-with-Handle**: 7-65주 형성, 핸들 8-12% 조정
- **Double Bottom**: W자형, 두 번째 저점에서 거래량 감소
- **Flat Base**: 5주+ 횡보, 15% 이내 조정
- **High Tight Flag**: 8주 내 100%+ 급등 후 10-25% 조정

### RAG (Retrieval-Augmented Generation)
- 각 CAN SLIM 모듈에 O'Neil 원문 규칙이 내장되어 있음
- AI가 실제 데이터를 원문 기준으로 직접 판단 (점수 산출 없음)

---

## ⚙️ 설치 및 실행

### 1. 환경 설정

```bash
# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows

# 의존성 설치
pip install -r requirements.txt
```

### 2. API 키 설정

`.env` 파일 생성:

```
GEMINI_API_KEY=your_gemini_api_key_here
```

### 3. 실행

```bash
python main.py
```

### 4. 사전 검증

```bash
python quick_test.py
```

---

## 📊 분석 예시

```
종목 코드 입력: NVDA
차트 유형: W (주봉)

→ RS Rating: 87/99 | Trend: RISING
→ Pattern: Cup-with-Handle (Quality: 85/100)
→ Buy Point: $138.42
→ Base Stage: 2
→ 최종 판단: BUY NOW (시장 선도주, 2차 베이스 돌파)
```

```
종목 코드 입력: 005930.KS  (삼성전자)
벤치마크: KOSPI 자동 선택
```

---

## 📦 주요 의존성

| 라이브러리 | 용도 |
|-----------|------|
| `yfinance` | 주가 데이터 수집 (Yahoo Finance) |
| `mplfinance` | 금융 차트 생성 |
| `pandas` | 데이터 처리 및 시계열 분석 |
| `google-generativeai` | Gemini AI API |
| `python-dotenv` | `.env` 파일 자동 로딩 |
| `Pillow` | 차트 이미지 처리 |

---

## 📝 버전 히스토리

| 버전 | 날짜 | 주요 변경사항 |
|------|------|-------------|
| **v2.1.0** | 2026-02-16 | CAN SLIM 모듈화, 한국어 리포트, RS 벤치마크 자동선택, Distribution Day, 다중종목 비교 |
| **v2.0.0** | 2026-02-05 | V2 패턴 감지 엔진 추가, 펀더멘털 분석 통합 |
| **v1.0.0** | 2026-01-01 | V1 기본 이미지 분석 |

---

## ⚠️ 면책 조항

이 프로젝트는 **교육 목적**으로 작성되었습니다.
투자 판단은 본인 책임이며, AI 분석 결과는 **참고용**입니다.
실제 투자 전 반드시 본인의 독립적인 판단과 전문가 조언을 구하십시오.

---

**Created by:** hyochang team
**Last Updated:** 2026-02-16
**License:** MIT (Educational Purpose)
