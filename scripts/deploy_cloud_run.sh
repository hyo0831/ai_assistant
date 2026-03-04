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

if [[ ! -d "$SRC_DIR" ]]; then
  echo "ERROR: source directory not found: $SRC_DIR"
  exit 1
fi

echo "[1/4] Set project: $PROJECT_ID"
gcloud config set project "$PROJECT_ID" >/dev/null

echo "[2/4] Enable required APIs"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com

echo "[3/4] Deploy Cloud Run service: $SERVICE_NAME"
cd "$SRC_DIR"
ENV_VARS=("GEMINI_API_KEY=$GEMINI_API_KEY")
if [[ -n "${OPENAI_API_KEY:-}" ]]; then
  ENV_VARS+=("OPENAI_API_KEY=$OPENAI_API_KEY")
fi
if [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
  ENV_VARS+=("ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY")
fi
if [[ -n "${GEMINI_MODEL:-}" ]]; then
  ENV_VARS+=("GEMINI_MODEL=$GEMINI_MODEL")
fi
if [[ -n "${OPENAI_MODEL:-}" ]]; then
  ENV_VARS+=("OPENAI_MODEL=$OPENAI_MODEL")
fi
if [[ -n "${ANTHROPIC_MODEL:-}" ]]; then
  ENV_VARS+=("ANTHROPIC_MODEL=$ANTHROPIC_MODEL")
fi

gcloud run deploy "$SERVICE_NAME" \
  --source . \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --update-env-vars "$(IFS=,; echo "${ENV_VARS[*]}")"

echo "[4/4] Done"
gcloud run services describe "$SERVICE_NAME" \
  --region "$REGION" \
  --platform managed \
  --format='value(status.url)'
