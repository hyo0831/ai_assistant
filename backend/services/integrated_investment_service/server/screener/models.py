from pydantic import BaseModel, Field
from typing import Optional


class ScreenerRequest(BaseModel):
    market: str = Field(default="US", description="현재 US만 지원")
    min_market_cap: float = Field(default=500_000_000, description="최소 시가총액(USD)")
    sort_by: str = Field(default="score", description="정렬: score/rs/eps_growth/revenue_growth/from_high")
    max_results: int = Field(default=100, description="반환 결과 수")
    provider: str = Field(default="claude", description="AI 제공자: gemini/openai/claude")
    prefilter_count: int = Field(default=160, description="1차 후보 선별 수")
    ai_rerank_count: int = Field(default=100, description="AI 0~99 점수 재평가할 종목 수")
    use_cache: bool = Field(default=True, description="캐시 사용 여부")
    force_refresh: bool = Field(default=False, description="캐시 무시 후 재계산")


class ScreenerRefreshRequest(BaseModel):
    secret: Optional[str] = Field(default=None, description="갱신 보호 토큰")
    provider: str = Field(default="claude", description="AI 제공자")
    min_market_cap: float = Field(default=500_000_000, description="최소 시가총액(USD)")
    max_results: int = Field(default=100, description="반환 결과 수")
