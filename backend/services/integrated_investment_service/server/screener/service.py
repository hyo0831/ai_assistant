from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Callable

from fastapi import HTTPException

from .models import ScreenerRefreshRequest, ScreenerRequest


class ScreenerService:
    def __init__(
        self,
        *,
        load_cache: Callable[[], dict | None],
        save_cache: Callable[[dict], None],
        refresh_state_snapshot: Callable[[], dict],
        start_refresh: Callable[[ScreenerRequest], bool],
        build_refresh_scan_request: Callable[[str, float, int], ScreenerRequest],
        bootstrap_cache_fast: Callable[[ScreenerRequest], dict],
        sort_rows: Callable[[list[dict], str], list[dict]],
        dedupe_rows: Callable[[list[dict]], tuple[list[dict], int]],
        is_default_cache_request: Callable[[ScreenerRequest], bool],
        attach_summaries: Callable[[list[dict], str], list[dict]],
        start_summary_backfill: Callable[[str, int], bool],
        compute_screener: Callable[[ScreenerRequest], dict],
        default_provider: str,
        refresh_policy: str,
    ):
        self._load_cache = load_cache
        self._save_cache = save_cache
        self._refresh_state_snapshot = refresh_state_snapshot
        self._start_refresh = start_refresh
        self._build_refresh_scan_request = build_refresh_scan_request
        self._bootstrap_cache_fast = bootstrap_cache_fast
        self._sort_rows = sort_rows
        self._dedupe_rows = dedupe_rows
        self._is_default_cache_request = is_default_cache_request
        self._attach_summaries = attach_summaries
        self._start_summary_backfill = start_summary_backfill
        self._compute_screener = compute_screener
        self._default_provider = default_provider
        self._refresh_policy = refresh_policy

    async def cache_status(self) -> dict[str, Any]:
        cache = self._load_cache()
        refresh_state = self._refresh_state_snapshot()
        if not cache:
            return {
                "ready": False,
                "refresh_policy": self._refresh_policy,
                "refresh_state": refresh_state,
            }
        return {
            "ready": True,
            "analyzed_at": cache.get("analyzed_at"),
            "result_count": len(cache.get("results", [])),
            "provider": cache.get("provider", self._default_provider),
            "refresh_policy": self._refresh_policy,
            "refresh_state": refresh_state,
        }

    async def refresh_status(self) -> dict[str, Any]:
        return {
            "refresh_state": self._refresh_state_snapshot(),
            "refresh_policy": self._refresh_policy,
        }

    async def refresh(self, req: ScreenerRefreshRequest) -> dict[str, Any]:
        token = os.environ.get("SCREENER_REFRESH_TOKEN")
        if token and req.secret != token:
            raise HTTPException(status_code=403, detail="refresh token mismatch")

        scan_req = self._build_refresh_scan_request(
            provider=req.provider,
            min_market_cap=req.min_market_cap,
            max_results=req.max_results,
        )
        started = self._start_refresh(scan_req)
        if not started:
            return {
                "accepted": False,
                "running": True,
                "detail": "refresh already in progress",
                "refresh_policy": self._refresh_policy,
                "refresh_state": self._refresh_state_snapshot(),
            }
        return {
            "accepted": True,
            "running": True,
            "detail": "refresh job started",
            "refresh_policy": self._refresh_policy,
            "refresh_state": self._refresh_state_snapshot(),
        }

    async def scan(self, req: ScreenerRequest) -> dict[str, Any]:
        sort_by = (req.sort_by or "score").lower()
        max_results = max(1, min(int(req.max_results), 100))
        cache = self._load_cache()
        use_cache = bool(req.use_cache) and not bool(req.force_refresh)
        default_cache_req = self._is_default_cache_request(req)
        refresh_state = self._refresh_state_snapshot()

        if default_cache_req and not cache:
            scan_req = self._build_refresh_scan_request(
                provider=req.provider,
                min_market_cap=req.min_market_cap,
                max_results=req.max_results,
            )
            bootstrap = self._bootstrap_cache_fast(scan_req)
            self._save_cache(bootstrap)
            started = self._start_refresh(scan_req)
            boot_rows = self._sort_rows(bootstrap.get("results", []), sort_by)
            boot_rows, dup_removed = self._dedupe_rows(boot_rows)
            return {
                **{k: v for k, v in bootstrap.items() if k != "results"},
                "results": boot_rows[:max_results],
                "duplicates_removed": dup_removed,
                "cache_hit": False,
                "ready": True,
                "refresh_started": started,
                "refresh_state": self._refresh_state_snapshot(),
                "refresh_policy": self._refresh_policy,
                "detail": "bootstrap cache ready; refresh started",
                "timestamp": datetime.utcnow().isoformat(),
            }

        if bool(req.force_refresh) and default_cache_req:
            scan_req = self._build_refresh_scan_request(
                provider=req.provider,
                min_market_cap=req.min_market_cap,
                max_results=req.max_results,
            )
            started = self._start_refresh(scan_req)
            if cache:
                cached_rows = self._sort_rows(cache.get("results", []), sort_by)
                cached_rows, dup_removed = self._dedupe_rows(cached_rows)
                return {
                    **{k: v for k, v in cache.items() if k != "results"},
                    "results": cached_rows[:max_results],
                    "duplicates_removed": dup_removed,
                    "cache_hit": True,
                    "refresh_started": started,
                    "refresh_state": self._refresh_state_snapshot(),
                    "refresh_policy": self._refresh_policy,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            return {
                "cache_hit": False,
                "refresh_started": started,
                "refresh_state": self._refresh_state_snapshot(),
                "refresh_policy": self._refresh_policy,
                "detail": "refresh started; cache not ready yet",
                "results": [],
                "timestamp": datetime.utcnow().isoformat(),
            }

        if use_cache and cache and default_cache_req:
            cached_rows = self._sort_rows(cache.get("results", []), sort_by)
            target_rows = cached_rows[:max_results]
            missing_summary = [r for r in target_rows if not str(r.get("summary", "")).strip()]
            if missing_summary:
                provider_for_summary = (req.provider or cache.get("provider") or self._default_provider).lower()
                self._attach_summaries(missing_summary[: min(3, len(missing_summary))], provider=provider_for_summary)
                if len(missing_summary) > 3:
                    self._start_summary_backfill(provider=provider_for_summary, max_rows=max_results)
                try:
                    updated_by_symbol = {str(r.get("symbol", "")).upper(): r for r in target_rows if r.get("symbol")}
                    base_rows = list(cache.get("results", []))
                    for row in base_rows:
                        sym = str(row.get("symbol", "")).upper()
                        if sym in updated_by_symbol:
                            row["summary"] = str(updated_by_symbol[sym].get("summary", "") or "")
                    cache["results"] = base_rows
                    self._save_cache(cache)
                    cached_rows = self._sort_rows(cache.get("results", []), sort_by)
                except Exception:
                    pass
            cached_rows, dup_removed = self._dedupe_rows(cached_rows)
            return {
                **{k: v for k, v in cache.items() if k != "results"},
                "results": cached_rows[:max_results],
                "duplicates_removed": dup_removed,
                "cache_hit": True,
                "refresh_state": refresh_state,
                "refresh_policy": self._refresh_policy,
                "timestamp": datetime.utcnow().isoformat(),
            }

        data = self._compute_screener(req)
        data["cache_hit"] = False
        data["refresh_policy"] = self._refresh_policy

        if default_cache_req:
            self._save_cache(data)

        data["refresh_state"] = self._refresh_state_snapshot()
        return data
