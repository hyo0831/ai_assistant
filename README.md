# AI Assistant Project

AI 투자 분석 서비스를 단일 프로젝트 구조로 정리한 모노레포입니다.

## Top-Level Structure

- `frontend/`
  - `chart_canslim_ui/`: 차트 기반 분석 UI
  - `integrated_ui/`: 통합 서비스 UI

- `backend/services/`
  - `chart_canslim_service/`: 차트 + 패턴 + CAN SLIM 분석 백엔드
  - `integrated_investment_service/`: 통합 API 서버(트레이딩 + 펀더멘털)
  - `kis_trading_diagnostics/`: KIS 거래내역 기반 매매 진단

## Quick Start

- Chart CANSLIM 서비스
  - `cd backend/services/chart_canslim_service`
  - `python main.py`
  - API: `uvicorn api:app --reload`

- Integrated 서비스
  - `cd backend/services/integrated_investment_service`
  - `python main.py`
  - API: `uvicorn server.app:app --reload`

- KIS 진단 서비스
  - `cd backend/services/kis_trading_diagnostics`
  - `python main.py`

## Run From Root

- 의존성 설치
  - `make install-all`

- API 실행
  - `make run-integrated-api`  (http://localhost:8000)
  - `make run-chart-api`       (http://localhost:8001)

- 정적 UI 실행
  - `make serve-integrated-ui` (http://localhost:3000)
  - `make serve-chart-ui`      (http://localhost:3001)

- CLI 실행
  - `make run-integrated-cli`
  - `make run-chart-cli`
  - `make run-kis-cli`

## Legacy Mapping

- `hyochang` -> `backend/services/chart_canslim_service`
- `yanghee` -> `backend/services/integrated_investment_service`
- `yongaa` -> `backend/services/kis_trading_diagnostics`
