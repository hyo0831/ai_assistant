from pydantic import BaseModel, Field
from typing import Literal, List, Dict, Optional

Market = Literal["KOSPI", "KOSDAQ", "NYSE", "NASDAQ", "AMEX", "ALL"]
Horizon = Literal["day", "swing", "long"]

class UserIntent(BaseModel):
    market: Market
    goal: str = Field(..., description="사용자가 찾고 싶은 종목의 성격/니즈 (예: 유동성 높은 단타, 저평가 우량, 모멘텀 등)")
    horizon: Horizon
    theme: Optional[str] = Field(None, description="최근 이슈/테마 (예: AI 반도체, 2차전지, 우주, 방산 등)")

class ConditionRule(BaseModel):
    id: int
    key: str
    op: Literal[">=", "<=", "between", "cross"]
    value: Optional[float] = None
    min: Optional[float] = None
    max: Optional[float] = None
    meta: Dict[str, str] = Field(default_factory=dict)

class FormulaRecommendation(BaseModel):
    formula_name: str
    formula_short_desc: str
    rules: List[ConditionRule]
    weights: Dict[str, float] = Field(default_factory=dict, description="조건별 가중치 (key->weight)")
    explanation_by_rule: Dict[str, str] = Field(default_factory=dict, description="각 조건이 왜 필요한지 설명")
    indicator_help: Dict[str, str] = Field(default_factory=dict, description="지표별 도움말(쉽게)")
    theme_hint: Optional[str] = None

class RankedStock(BaseModel):
    symbol: str
    name: str
    market: str
    condition_score: float
    theme_score: float
    total_score: float
    why: str
    tags: List[str] = Field(default_factory=list)
    rule_breakdown: Dict[str, Dict[str, object]] = Field(default_factory=dict)
    theme_brief: Optional[str] = None
    news_items: List[Dict[str, str]] = Field(default_factory=list)

class RecommendResponse(BaseModel):
    intent: UserIntent
    recommendation: FormulaRecommendation
    top: List[RankedStock]
    as_of: str
    note: Optional[str] = None
