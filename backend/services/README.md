# Backend Services

## 서비스 구성

| 서비스 | 경로 | 상태 | 설명 |
|--------|------|------|------|
| `integrated_investment_service` | `backend/services/integrated_investment_service/` | ✅ **프로덕션** | 통합 API (스크리너 + 차트 분석 + 펀더멘털) |
| `chart_canslim_service` | `backend/services/chart_canslim_service/` | 🗄️ **레거시** | 독립 실행 프로토타입 (CLI + 단독 API) |
| `kis_trading_diagnostics` | `backend/services/kis_trading_diagnostics/` | ✅ 운영 중 | KIS 체결 기반 매매 성향 진단 |

## 관계

`chart_canslim_service`는 원본 프로토타입으로, 차트 분석 로직이 `integrated_investment_service/trading/`으로 이식되었습니다.
현재 통합 서비스는 `chart_canslim_service`를 import하지 않으며, 내부 `trading/` 모듈을 직접 사용합니다.

## 실행

루트에서 `make` 명령어 사용을 권장합니다:

```bash
make run-integrated-api     # :8000 (메인 API)
make serve-integrated-ui    # :3000 (웹 UI)
```
