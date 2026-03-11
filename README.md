# 📈 AI 기반 CAN SLIM 투자 분석 플랫폼

> William O'Neil의 CAN SLIM 방법론을 AI로 구현한 미국 주식 스크리너 & 분석 플랫폼

![Version](https://img.shields.io/badge/version-1.0.0-blue) ![Python](https://img.shields.io/badge/python-3.11+-green) ![License](https://img.shields.io/badge/license-MIT-lightgrey)

## 소개

William O'Neil의 **CAN SLIM** 방법론을 기반으로 S&P500 + NASDAQ 전 종목을 자동으로 스크리닝하고 AI가 재랭킹하는 투자 분석 플랫폼입니다. Gemini / OpenAI / Claude 멀티 AI 프로바이더를 지원하며, 차트 패턴 감지부터 펀더멘털 분석까지 통합 제공합니다.

## 🔍 CAN SLIM 방법론

| 항목 | 의미 | 기준 |
|------|------|------|
| **C** – Current Earnings | 최근 분기 EPS 성장 | 25%+ |
| **A** – Annual Earnings | 연간 EPS 성장 (3년) | 25%+ |
| **N** – New Product/High | 신제품 또는 52주 신고가 | 신고가 근접 |
| **S** – Supply & Demand | 주식 수급 (거래량 급증) | 평균 대비 50%+ |
| **L** – Leader or Laggard | 섹터 내 선도주 여부 | RS Rating 85+ |
| **I** – Institutional Sponsorship | 기관 매수 증가 | 기관 지분 증가 추세 |
| **M** – Market Direction | 시장 방향성 (S&P500) | 상승 추세 확인 |

## ✨ 핵심 기능

- **🔍 스크리너**: S&P500 + NASDAQ 전종목 → 시총 $500M+ 필터 → CAN SLIM 점수화 → AI 재랭킹 → 상위 100종목
- **📊 차트 분석**: Cup-with-Handle, Flat Base 등 패턴 감지 + AI 해석 및 매수 시점 제안
- **🎯 트레이딩 판정**: BUY NOW / WATCH & WAIT / AVOID 3단계 판정
- **📈 RS Rating**: S&P500 대비 상대 강도(Relative Strength) 계산
- **🤖 멀티 AI**: Gemini 2.5 Flash / GPT-4 / Claude 실시간 전환

## 🚀 스크리닝 파이프라인

```
전체 종목 (S&P500 + NASDAQ)
  → 시총 $500M+ 필터
  → CAN SLIM 지표 수집 (EPS 성장, 매출 성장, RS Rating, 거래량 등)
  → AI 재랭킹 (0–99점)
  → 상위 100종목 반환
```

**캐시 전략**: 캐시 우선 반환 → 백그라운드 점진적 갱신 (1회당 20종목 보강)

**스케줄러**:
- 사전 갱신: 금/토/일 20분 간격
- 최종 갱신: 월요일 09:00 (KST)

## ⚡ 빠른 시작

```bash
# 1. 의존성 설치
make install-all

# 2. 환경변수 설정
cp .env.example .env  # GEMINI_API_KEY 필수, OPENAI/ANTHROPIC 선택

# 3. 서버 실행
make run-integrated-api   # API  → http://localhost:8000
make serve-integrated-ui  # UI   → http://localhost:3000
```

**.env 예시**:
```env
GEMINI_API_KEY=your_gemini_key
OPENAI_API_KEY=your_openai_key      # optional
ANTHROPIC_API_KEY=your_claude_key   # optional
```

## 📡 API 엔드포인트

| 경로 | 메서드 | 설명 |
|------|--------|------|
| `/api/screener/scan` | POST | 스크리너 실행 (캐시 우선) |
| `/api/screener/refresh` | POST | 백그라운드 갱신 트리거 |
| `/api/screener/cache/status` | GET | 캐시 상태 조회 |
| `/api/trading/analyze` | POST | 차트 + 패턴 + CAN SLIM 분석 |
| `/api/analysis/analyze` | POST | 펀더멘털 CAN SLIM 분석 |
| `/api/providers/status` | GET | AI 프로바이더 키 상태 |
| `/health` | GET | 헬스체크 |

## 🗂️ 프로젝트 구조

```
ai_assistant/
├── backend/services/
│   ├── integrated_investment_service/   # 핵심 API 서버 (FastAPI, :8000)
│   │   └── server/
│   │       ├── app.py                   # 메인 앱
│   │       └── screener/                # 스크리너 모듈
│   ├── chart_canslim_service/           # 차트 분석 서비스
│   └── kis_trading_diagnostics/         # KIS 진단 서비스
├── frontend/integrated_ui/              # 통합 웹 UI (:3000)
├── scripts/deploy_cloud_run.sh
└── Makefile
```

## ☁️ Cloud Run 배포

```bash
export GEMINI_API_KEY=...
export OPENAI_API_KEY=...      # optional
export ANTHROPIC_API_KEY=...   # optional
./scripts/deploy_cloud_run.sh <PROJECT_ID> <REGION>
```

예시:
```bash
./scripts/deploy_cloud_run.sh ai-assistant-489106 asia-northeast3
```
