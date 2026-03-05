from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Optional


class ScreenerCacheStore:
    def __init__(self, cache_file: Path):
        self.cache_file = cache_file
        self._lock = threading.Lock()

    def load(self) -> Optional[dict]:
        with self._lock:
            if not self.cache_file.exists():
                return None
            try:
                with open(self.cache_file, "r") as f:
                    return json.load(f)
            except Exception:
                return None

    def save(self, payload: dict):
        with self._lock:
            with open(self.cache_file, "w") as f:
                json.dump(payload, f, ensure_ascii=False)


def load_json_file(path: Path) -> Optional[dict]:
    try:
        if not path.exists():
            return None
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return None


def save_json_file(path: Path, payload: dict):
    with open(path, "w") as f:
        json.dump(payload, f, ensure_ascii=False)
