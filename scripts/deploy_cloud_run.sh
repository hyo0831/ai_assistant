#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <PROJECT_ID> [REGION]"
  exit 1
fi

PROJECT_ID="$1"
REGION="${2:-asia-northeast3}"
SERVICE_NAME="ai-assistant-api"
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SRC_DIR="$ROOT_DIR/backend/services/integrated_investment_service"

if [[ -z "${GEMINI_API_KEY:-}" ]]; then
  echo "ERROR: GEMINI_API_KEY is not set."
  echo "Run: export GEMINI_API_KEY='your_key'"
  exit 1
fi

if [[ -z "${SCHEDULER_SECRET:-}" ]]; then
  echo "ERROR: SCHEDULER_SECRET is not set."
  echo "Run: export SCHEDULER_SECRET='\$(openssl rand -hex 32)'"
  exit 1
fi

if [[ ! -d "$SRC_DIR" ]]; then
  echo "ERROR: source directory not found: $SRC_DIR"
  exit 1
fi

echo "[1/5] Set project: $PROJECT_ID"
gcloud config set project "$PROJECT_ID" >/dev/null

echo "[2/5] Enable required APIs"
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  cloudscheduler.googleapis.com

echo "[3/5] Deploy Cloud Run service: $SERVICE_NAME"
cd "$SRC_DIR"
ENV_VARS=("GEMINI_API_KEY=$GEMINI_API_KEY" "SCHEDULER_SECRET=$SCHEDULER_SECRET")
if [[ -n "${OPENAI_API_KEY:-}" ]];    then ENV_VARS+=("OPENAI_API_KEY=$OPENAI_API_KEY"); fi
if [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then ENV_VARS+=("ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY"); fi
if [[ -n "${GEMINI_MODEL:-}" ]];      then ENV_VARS+=("GEMINI_MODEL=$GEMINI_MODEL"); fi
if [[ -n "${OPENAI_MODEL:-}" ]];      then ENV_VARS+=("OPENAI_MODEL=$OPENAI_MODEL"); fi
if [[ -n "${ANTHROPIC_MODEL:-}" ]];   then ENV_VARS+=("ANTHROPIC_MODEL=$ANTHROPIC_MODEL"); fi
if [[ -n "${GCS_BUCKET:-}" ]];        then ENV_VARS+=("GCS_BUCKET=$GCS_BUCKET"); fi

gcloud run deploy "$SERVICE_NAME" \
  --source . \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --timeout=3600 \
  --update-env-vars "$(IFS=,; echo "${ENV_VARS[*]}")"

echo "[4/5] Get service URL"
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
  --region "$REGION" \
  --platform managed \
  --format='value(status.url)')
echo "Service URL: $SERVICE_URL"

echo "[5/5] Register Cloud Scheduler jobs (KST = UTC+9)"
# 금 23:00 KST = 금 14:00 UTC
gcloud scheduler jobs create http screener-refresh-universe \
  --location="$REGION" \
  --schedule="0 14 * * 5" \
  --uri="${SERVICE_URL}/internal/scheduler/refresh-universe" \
  --http-method=POST \
  --headers="X-Scheduler-Secret=${SCHEDULER_SECRET}" \
  --attempt-deadline=600s \
  --time-zone="UTC" \
  --project="$PROJECT_ID" 2>/dev/null || \
gcloud scheduler jobs update http screener-refresh-universe \
  --location="$REGION" \
  --schedule="0 14 * * 5" \
  --uri="${SERVICE_URL}/internal/scheduler/refresh-universe" \
  --http-method=POST \
  --headers="X-Scheduler-Secret=${SCHEDULER_SECRET}" \
  --attempt-deadline=600s \
  --time-zone="UTC" \
  --project="$PROJECT_ID"

# 일 01:00 KST = 토 16:00 UTC  (~15분 소요)
gcloud scheduler jobs create http screener-collect-prices \
  --location="$REGION" \
  --schedule="0 16 * * 6" \
  --uri="${SERVICE_URL}/internal/scheduler/collect-prices" \
  --http-method=POST \
  --headers="X-Scheduler-Secret=${SCHEDULER_SECRET}" \
  --attempt-deadline=1800s \
  --time-zone="UTC" \
  --project="$PROJECT_ID" 2>/dev/null || \
gcloud scheduler jobs update http screener-collect-prices \
  --location="$REGION" \
  --schedule="0 16 * * 6" \
  --uri="${SERVICE_URL}/internal/scheduler/collect-prices" \
  --http-method=POST \
  --headers="X-Scheduler-Secret=${SCHEDULER_SECRET}" \
  --attempt-deadline=1800s \
  --time-zone="UTC" \
  --project="$PROJECT_ID"

# 일 03:00 KST = 토 18:00 UTC  (~3분 소요)
gcloud scheduler jobs create http screener-score-fundamentals \
  --location="$REGION" \
  --schedule="0 18 * * 6" \
  --uri="${SERVICE_URL}/internal/scheduler/score-fundamentals" \
  --http-method=POST \
  --headers="X-Scheduler-Secret=${SCHEDULER_SECRET}" \
  --attempt-deadline=600s \
  --time-zone="UTC" \
  --project="$PROJECT_ID" 2>/dev/null || \
gcloud scheduler jobs update http screener-score-fundamentals \
  --location="$REGION" \
  --schedule="0 18 * * 6" \
  --uri="${SERVICE_URL}/internal/scheduler/score-fundamentals" \
  --http-method=POST \
  --headers="X-Scheduler-Secret=${SCHEDULER_SECRET}" \
  --attempt-deadline=600s \
  --time-zone="UTC" \
  --project="$PROJECT_ID"

# 월 09:00 KST = 월 00:00 UTC
gcloud scheduler jobs create http screener-publish-cache \
  --location="$REGION" \
  --schedule="0 0 * * 1" \
  --uri="${SERVICE_URL}/internal/scheduler/publish-cache" \
  --http-method=POST \
  --headers="X-Scheduler-Secret=${SCHEDULER_SECRET}" \
  --attempt-deadline=600s \
  --time-zone="UTC" \
  --project="$PROJECT_ID" 2>/dev/null || \
gcloud scheduler jobs update http screener-publish-cache \
  --location="$REGION" \
  --schedule="0 0 * * 1" \
  --uri="${SERVICE_URL}/internal/scheduler/publish-cache" \
  --http-method=POST \
  --headers="X-Scheduler-Secret=${SCHEDULER_SECRET}" \
  --attempt-deadline=600s \
  --time-zone="UTC" \
  --project="$PROJECT_ID"

echo ""
echo "===== Deploy complete ====="
echo "Service URL : $SERVICE_URL"
echo "Scheduler   : 4 jobs registered (refresh-universe / collect-prices / score-fundamentals / publish-cache)"
