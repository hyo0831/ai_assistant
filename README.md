# AI Assistant Monorepo

AI 투자 분석 서비스(트레이딩 + 펀더멘털 + 스크리너) 모노레포입니다.

## Structure

- `frontend/integrated_ui/`: 통합 웹 UI
- `backend/services/integrated_investment_service/`: 통합 API 서버(FastAPI)
- `backend/services/chart_canslim_service/`: 차트 중심 분석 서비스
- `backend/services/kis_trading_diagnostics/`: KIS 진단 서비스
- `scripts/deploy_cloud_run.sh`: Cloud Run 배포 스크립트

## Integrated Service (핵심)

경로: `backend/services/integrated_investment_service`

- `server/app.py`
  - `POST /api/trading/analyze`: 차트 + 패턴 + CAN SLIM 분석
  - `POST /api/analysis/analyze`: 펀더멘털 CAN SLIM 분석
  - `POST /api/screener/scan`: 스크리너 조회(기본은 캐시 우선)
  - `POST /api/screener/refresh`: 스크리너 캐시 강제 갱신
  - `GET /api/screener/cache/status`: 캐시 상태 확인
  - `GET /api/providers/status`: Gemini/OpenAI/Claude 키 상태
  - `GET /health`: 헬스체크

## Screener 운영 정책

- 기본 유니버스: `S&P500 + NASDAQ (all)`
- 기본 필터: `min_market_cap = 500,000,000 USD`
- 기본 결과 수: `100`
- 기본 제공자: `claude`
- 캐시 정책: 기본 요청은 캐시 우선 반환
- 갱신 정책: `매주 월요일 오전 9시 (KST)` 스케줄러 갱신
- 설계 의도: 대유니버스 호출은 저속 배치(phase1/phase2)로 분산해 rate limit 완화

주의:
- Yahoo 소스는 짧은 시간 burst 호출 시 rate limit가 발생할 수 있습니다.
- 일부 종목의 시총/EPS 성장값이 제한될 수 있으며, 이 경우 UI에서 `데이터 제한`으로 표시됩니다.

## Local Run

1. 의존성 설치
- `make install-all`

2. 통합 API 실행
- `make run-integrated-api`
- 기본 주소: `http://localhost:8000`

3. 통합 UI 실행
- `make serve-integrated-ui`
- 기본 주소: `http://localhost:3000`

## Cloud Run Deploy

프로젝트 루트에서:

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
