from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Optional

from .gcs import load_json as gcs_load_json, save_json as gcs_save_json

_CACHE_BLOB = "screener/cache.json"


class ScreenerCacheStore:
    def __init__(self, cache_file: Path):
        self.cache_file = cache_file
        self._lock = threading.Lock()

    def load(self) -> Optional[dict]:
        with self._lock:
            data = gcs_load_json(_CACHE_BLOB, self.cache_file)
            return data

    def save(self, payload: dict):
        with self._lock:
            gcs_save_json(_CACHE_BLOB, self.cache_file, payload)


def load_json_file(path: Path) -> Optional[dict]:
    return gcs_load_json(_CACHE_BLOB, path)


def save_json_file(path: Path, payload: dict):
    gcs_save_json(_CACHE_BLOB, path, payload)
