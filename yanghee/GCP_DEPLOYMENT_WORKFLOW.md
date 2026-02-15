# GCP 배포 워크플로우 (Google Cloud Platform Deployment)

## 프로젝트 개요

**윌리엄 오닐 AI 투자 어시스턴트**를 Google Cloud Platform에 배포하여 REST API 백엔드로 서비스합니다.

- **현재 상태**: CLI 기반 로컬 실행 (input() 기반 대화형)
- **목표 상태**: Cloud Run 기반 REST API 서비스

---

## 아키텍처 Overview

```
[프론트엔드 (다른 팀원)]
        │
        ▼
┌─────────────────────────────┐
│   Cloud Run (FastAPI)       │  ← 백엔드 API 서버
│   - /analyze (POST)         │
│   - /health (GET)           │
├─────────────────────────────┤
│   내부 모듈                  │
│   - main.py (분석 로직)      │
│   - pattern_detector.py     │
│   - system_prompt.py        │
│   - feedback_manager.py     │
└────────┬────────────────────┘
         │
    ┌────┴────────────┐
    ▼                 ▼
Secret Manager    Cloud Storage
(GEMINI_API_KEY)  (차트 이미지, 피드백)
```

---

## Phase 1: API 서버 구축 (로컬 개발)

### 1-1. FastAPI 래핑

현재 CLI 기반 `main.py`를 REST API로 전환합니다.

**작업 내용:**
- [ ] `app.py` 생성 — FastAPI 엔트리포인트
- [ ] `POST /analyze` 엔드포인트 구현
  - Request Body: `{ "ticker": "AAPL", "mode": "v1" | "v2", "interval": "1wk" | "1d" }`
  - Response: `{ "analysis": "...", "pattern_data": {...}, "chart_url": "..." }`
- [ ] `GET /health` 헬스체크 엔드포인트
- [ ] `input()` 호출 제거 — API 파라미터로 대체
- [ ] 차트 이미지를 Base64 또는 Cloud Storage URL로 반환
- [ ] 에러 핸들링 (유효하지 않은 ticker, API 키 오류 등)

**신규 파일:**
```
app.py              # FastAPI 앱 + 라우터
```

**requirements.txt 추가:**
```
fastapi>=0.104.0
uvicorn>=0.24.0
python-multipart>=0.0.6
```

### 1-2. 로컬 테스트

```bash
# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 의존성 설치
pip install -r requirements.txt

# 로컬 실행
uvicorn app:app --reload --port 8080

# 테스트
curl -X POST http://localhost:8080/analyze \
  -H "Content-Type: application/json" \
  -d '{"ticker": "AAPL", "mode": "v2"}'
```

---

## Phase 2: Docker 컨테이너화

### 2-1. Dockerfile 작성

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 시스템 의존성 (matplotlib 등에 필요)
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run은 PORT 환경변수를 사용
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
```

### 2-2. .dockerignore 작성

```
__pycache__/
*.pyc
venv/
.env
*.png
feedback/
.git/
.claude/
```

### 2-3. 로컬 Docker 테스트

```bash
docker build -t oneil-ai .
docker run -p 8080:8080 -e GEMINI_API_KEY="your-key" oneil-ai
```

---

## Phase 3: GCP 인프라 설정

### 3-1. GCP 프로젝트 초기설정

```bash
# gcloud CLI 로그인
gcloud auth login

# 프로젝트 설정 (프로젝트 ID는 팀과 합의 필요)
gcloud config set project [PROJECT_ID]

# 필요한 API 활성화
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  artifactregistry.googleapis.com
```

### 3-2. Secret Manager에 API 키 등록

```bash
# GEMINI_API_KEY를 Secret Manager에 저장
echo -n "your-gemini-api-key" | \
  gcloud secrets create GEMINI_API_KEY --data-file=-

# Cloud Run 서비스 계정에 접근 권한 부여
gcloud secrets add-iam-policy-binding GEMINI_API_KEY \
  --member="serviceAccount:[PROJECT_NUMBER]-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### 3-3. Artifact Registry 저장소 생성

```bash
gcloud artifacts repositories create oneil-ai-repo \
  --repository-format=docker \
  --location=asia-northeast3 \
  --description="O'Neil AI Docker images"
```

---

## Phase 4: Cloud Run 배포

### 4-1. 컨테이너 이미지 빌드 및 푸시

```bash
# Cloud Build로 이미지 빌드
gcloud builds submit --tag asia-northeast3-docker.pkg.dev/[PROJECT_ID]/oneil-ai-repo/oneil-ai:latest
```

### 4-2. Cloud Run 서비스 배포

```bash
gcloud run deploy oneil-ai \
  --image asia-northeast3-docker.pkg.dev/[PROJECT_ID]/oneil-ai-repo/oneil-ai:latest \
  --region asia-northeast3 \
  --platform managed \
  --allow-unauthenticated \
  --set-secrets GEMINI_API_KEY=GEMINI_API_KEY:latest \
  --memory 1Gi \
  --timeout 120 \
  --max-instances 5
```

> **참고**: `--allow-unauthenticated`는 개발/테스트 용도입니다. 프로덕션에서는 인증을 추가해야 합니다.

### 4-3. 배포 확인

```bash
# 서비스 URL 확인
gcloud run services describe oneil-ai --region asia-northeast3 --format='value(status.url)'

# API 테스트
curl -X POST https://[SERVICE_URL]/analyze \
  -H "Content-Type: application/json" \
  -d '{"ticker": "AAPL", "mode": "v2"}'
```

---

## Phase 5: CI/CD 파이프라인 (선택)

### GitHub Actions 워크플로우

`.github/workflows/deploy.yml` 파일을 생성하여 main 브랜치 푸시 시 자동 배포합니다.

```yaml
name: Deploy to Cloud Run

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - id: auth
        uses: google-github-actions/auth@v2
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}

      - uses: google-github-actions/setup-gcloud@v2

      - name: Build and Push
        run: |
          gcloud builds submit \
            --tag asia-northeast3-docker.pkg.dev/${{ secrets.GCP_PROJECT_ID }}/oneil-ai-repo/oneil-ai:${{ github.sha }}

      - name: Deploy to Cloud Run
        run: |
          gcloud run deploy oneil-ai \
            --image asia-northeast3-docker.pkg.dev/${{ secrets.GCP_PROJECT_ID }}/oneil-ai-repo/oneil-ai:${{ github.sha }} \
            --region asia-northeast3 \
            --platform managed
```

---

## 작업 순서 요약

| 순서 | 작업 | 담당 | 상태 |
|------|------|------|------|
| 1 | FastAPI `app.py` 작성 | 백엔드 | 대기 |
| 2 | 로컬 API 테스트 | 백엔드 | 대기 |
| 3 | Dockerfile 작성 | 백엔드 | 대기 |
| 4 | Docker 로컬 테스트 | 백엔드 | 대기 |
| 5 | GCP 프로젝트 설정 | 백엔드 | 대기 |
| 6 | Secret Manager 설정 | 백엔드 | 대기 |
| 7 | Cloud Run 배포 | 백엔드 | 대기 |
| 8 | 프론트엔드 연동 테스트 | 프론트+백엔드 | 대기 |
| 9 | CI/CD 파이프라인 (선택) | 백엔드 | 대기 |

---

## API 명세 (프론트엔드 팀 참고)

### POST /analyze

주식 차트 분석 요청

**Request:**
```json
{
  "ticker": "AAPL",
  "mode": "v2",
  "interval": "1wk"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| ticker | string | O | 종목 코드 (예: "AAPL", "005930.KS") |
| mode | string | X | "v1" (기본 AI) 또는 "v2" (패턴감지+AI), 기본값 "v2" |
| interval | string | X | "1wk" (주봉) 또는 "1d" (일봉), 기본값 "1wk" |

**Response (200):**
```json
{
  "ticker": "AAPL",
  "mode": "v2",
  "analysis": "## CHART ANALYSIS: AAPL\n...",
  "pattern_data": {
    "best_pattern": {
      "type": "Cup-with-Handle",
      "quality_score": 75,
      "pivot_point": 198.50
    },
    "base_stage": { "estimated_stage": 2 },
    "volume_analysis": { "recent_volume_trend": "ACCUMULATION" },
    "rs_analysis": { "rs_rating": 87 }
  },
  "chart_base64": "data:image/png;base64,...",
  "timestamp": "2026-02-15T14:30:00"
}
```

**Response (400):**
```json
{
  "detail": "Invalid ticker symbol"
}
```

### GET /health

서버 상태 확인

**Response (200):**
```json
{
  "status": "healthy",
  "version": "2.0.0"
}
```

---

## 주의사항

1. **GEMINI_API_KEY**: 절대 코드에 하드코딩하지 말 것. Secret Manager 사용
2. **CORS**: 프론트엔드 도메인에 맞게 CORS 설정 필요
3. **타임아웃**: Gemini API 호출 + 차트 생성으로 응답 시간이 길 수 있음 (30~60초). Cloud Run 타임아웃을 120초로 설정
4. **메모리**: matplotlib 차트 생성 시 메모리 사용량이 높을 수 있으므로 최소 1Gi 할당
5. **리전**: `asia-northeast3` (서울) 사용으로 한국에서 빠른 응답

---

**작성일**: 2026-02-15
**작성자**: 백엔드 담당
**상태**: Phase 1부터 순차 진행 예정
