"""GCS JSON 읽기/쓰기 헬퍼.

환경변수 GCS_BUCKET이 설정된 경우 GCS 우선, 없으면 로컬 파일 폴백.
Cloud Run에서는 기본 서비스 계정으로 인증 자동 처리.
"""
from __future__ import annotations

import json
import os
from pathlib import Path


def _bucket_name() -> str:
    return os.environ.get("GCS_BUCKET", "")


def gcs_load(blob_name: str) -> dict | None:
    """GCS에서 JSON 파일 로드. 실패 시 None 반환."""
    bucket = _bucket_name()
    if not bucket:
        return None
    try:
        from google.cloud import storage
        client = storage.Client()
        blob = client.bucket(bucket).blob(blob_name)
        if not blob.exists():
            return None
        return json.loads(blob.download_as_text())
    except Exception as e:
        print(f"[gcs] load error ({blob_name}): {e}")
        return None


def gcs_save(blob_name: str, data: dict) -> bool:
    """GCS에 JSON 파일 저장. 성공 시 True 반환."""
    bucket = _bucket_name()
    if not bucket:
        return False
    try:
        from google.cloud import storage
        client = storage.Client()
        blob = client.bucket(bucket).blob(blob_name)
        blob.upload_from_string(
            json.dumps(data, ensure_ascii=False),
            content_type="application/json",
        )
        print(f"[gcs] saved → gs://{bucket}/{blob_name}")
        return True
    except Exception as e:
        print(f"[gcs] save error ({blob_name}): {e}")
        return False


def load_json(blob_name: str, local_path: Path) -> dict | None:
    """GCS 우선 로드, 없으면 로컬 파일 폴백."""
    data = gcs_load(blob_name)
    if data is not None:
        return data
    # 로컬 폴백 (개발 환경)
    try:
        if local_path.exists():
            return json.loads(local_path.read_text())
    except Exception:
        pass
    return None


def save_json(blob_name: str, local_path: Path, data: dict) -> None:
    """GCS 저장 + 로컬 파일 동시 저장."""
    gcs_save(blob_name, data)
    try:
        local_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    except Exception:
        pass
