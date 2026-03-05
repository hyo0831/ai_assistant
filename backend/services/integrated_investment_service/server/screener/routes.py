from typing import Any, Protocol

from fastapi import APIRouter

from .models import ScreenerRefreshRequest, ScreenerRequest


class ScreenerHandlers(Protocol):
    async def cache_status(self) -> dict[str, Any]: ...
    async def refresh_status(self) -> dict[str, Any]: ...
    async def refresh(self, req: ScreenerRefreshRequest) -> dict[str, Any]: ...
    async def scan(self, req: ScreenerRequest) -> dict[str, Any]: ...


def create_screener_router(handlers: ScreenerHandlers) -> APIRouter:
    router = APIRouter(tags=["screener"])

    @router.get("/api/screener/cache/status")
    async def screener_cache_status():
        return await handlers.cache_status()

    @router.get("/api/screener/refresh/status")
    async def screener_refresh_status():
        return await handlers.refresh_status()

    @router.post("/api/screener/refresh")
    async def screener_refresh(req: ScreenerRefreshRequest):
        return await handlers.refresh(req)

    @router.post("/api/screener/scan")
    async def screener_scan(req: ScreenerRequest):
        return await handlers.scan(req)

    return router
