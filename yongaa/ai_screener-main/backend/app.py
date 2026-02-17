from __future__ import annotations
import json
import os
from typing import Any, Dict, List
from datetime import date

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests
import feedparser
from urllib.parse import quote_plus

from openai import OpenAI

from schemas import UserIntent, RecommendResponse, FormulaRecommendation, ConditionRule, RankedStock
from logic import (
    load_universe,
    score_conditions,
    score_theme,
    build_ranked,
    explain_row,
    pick_rules_by_intent,
    default_formula_name,
    DEFAULT_INDICATOR_HELP,
    COND_KEYS,
    fill_rule_params,
    build_pass_mask,
    build_rule_breakdown,
)

load_dotenv()

DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "sample_universe.csv")
MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")
API_KEY = os.getenv("OPENAI_API_KEY", "").strip()

app = FastAPI(title="AI 투자도우미 - 조건검색편")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


def _build_system_prompt() -> str:
    return (
        "너는 투자 조건검색 공식을 설계하는 어시스턴트다. "
        "사용자 의도와 조건식(룰)을 보고 짧고 직관적인 공식 이름과 설명을 만든다. "
        "과장된 수익 보장은 피하고, 조건의 의미를 초보도 이해할 수 있게 설명한다."
    )


def _build_user_prompt(intent: UserIntent, rules: List[dict]) -> str:
    rules_txt = ", ".join([f"{r['key']}" for r in rules])
    return (
        f"사용자 의도:\n"
        f"- 시장: {intent.market}\n"
        f"- 목표: {intent.goal}\n"
        f"- 기간: {intent.horizon}\n"
        f"- 테마: {intent.theme or '없음'}\n\n"
        f"조건 키: {rules_txt}\n"
        f"조건 설명 키 매핑: {json.dumps(COND_KEYS, ensure_ascii=False)}\n\n"
        "아래 JSON만 출력:\n"
        "{\n"
        "  \"formula_name\": \"짧고 직관적인 공식 이름\",\n"
        "  \"formula_short_desc\": \"한 줄 설명\",\n"
        "  \"explanation_by_rule\": {\"key\": \"왜 이 조건이 필요한지 쉬운 설명\"},\n"
        "  \"indicator_help\": {\"key\": \"지표 도움말(초보자용)\"},\n"
        "  \"theme_hint\": \"테마 점수 해석 팁(있으면)\"\n"
        "}\n"
    )


def _call_llm(intent: UserIntent, rules: List[dict]) -> Dict[str, Any]:
    if not API_KEY:
        return {}

    client = OpenAI(api_key=API_KEY)

    try:
        resp = client.responses.create(
            model=MODEL,
            input=[
                {"role": "system", "content": _build_system_prompt()},
                {"role": "user", "content": _build_user_prompt(intent, rules)},
            ],
        )
        text = getattr(resp, "output_text", None) or ""
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except Exception:
        return {}
    return {}

def _summarize_theme(intent: UserIntent, top_rows: List[dict]) -> Dict[str, str]:
    if not API_KEY:
        return {}

    if not intent.theme:
        return {}

    client = OpenAI(api_key=API_KEY)
    items = [
        {
            "symbol": r["symbol"],
            "name": r["name"],
            "tags": r.get("tags", []),
        }
        for r in top_rows
    ]

    prompt = (
        "You are an assistant that writes SHORT speculative theme-fit notes.\n"
        "Avoid factual claims and avoid citing real news. Use hedged language like 'may' or 'could'.\n"
        "Return a JSON object: {\"items\": [{\"symbol\": \"\", \"summary\": \"\"}, ...]}.\n"
        f"Theme: {intent.theme}\n"
        f"Stocks: {json.dumps(items, ensure_ascii=False)}\n"
        "Write 1-2 sentences per stock. Respond in Korean.\n"
    )

    try:
        resp = client.responses.create(
            model=MODEL,
            input=[{"role": "user", "content": prompt}],
            text={"format": {"type": "json_object"}},
        )
        text = getattr(resp, "output_text", None) or ""
        data = json.loads(text)
        out = {}
        for item in data.get("items", []):
            sym = item.get("symbol")
            summ = item.get("summary")
            if sym and summ:
                out[str(sym)] = str(summ)
        return out
    except Exception:
        return {}

def _fetch_news(query: str, lang: str = "ko", max_items: int = 3) -> List[Dict[str, str]]:
    # Google News RSS (no API key)
    if not query:
        return []
    try:
        q = quote_plus(query)
        if lang == "ko":
            url = f"https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko"
        else:
            url = f"https://news.google.com/rss/search?q={q}&hl=en&gl=US&ceid=US:en"
        resp = requests.get(url, timeout=8)
        if resp.status_code != 200:
            return []
        feed = feedparser.parse(resp.text)
        items = []
        for e in feed.entries[:max_items]:
            items.append(
                {
                    "title": str(e.get("title", "")),
                    "link": str(e.get("link", "")),
                    "published": str(e.get("published", "")),
                }
            )
        return items
    except Exception:
        return []

def _summarize_news(items: List[Dict[str, str]], stock_name: str, theme: str | None) -> str | None:
    if not items:
        return None

    titles = [i.get("title", "") for i in items if i.get("title")]
    if not API_KEY:
        # API 키 없으면 타이틀 요약 대체
        return " / ".join(titles[:2])

    client = OpenAI(api_key=API_KEY)
    prompt = (
        "다음은 뉴스 제목 목록이다. 사실 단정은 피하고, "
        "해당 종목과 테마의 연관 가능성을 1-2문장으로 요약하라. "
        "근거는 제목에서만 가져와라.\n"
        f"종목: {stock_name}\n"
        f"테마: {theme or '없음'}\n"
        f"제목: {json.dumps(titles, ensure_ascii=False)}\n"
        "한국어로 작성."
    )
    try:
        resp = client.responses.create(
            model=MODEL,
            input=[{"role": "user", "content": prompt}],
        )
        text = getattr(resp, "output_text", None) or ""
        return text.strip()
    except Exception:
        return None

def _build_recommendation(intent: UserIntent, rules: List[dict]) -> FormulaRecommendation:
    fallback_name = default_formula_name(intent.horizon, intent.market)
    llm = _call_llm(intent, rules)

    rec = FormulaRecommendation(
        formula_name=llm.get("formula_name", fallback_name),
        formula_short_desc=llm.get("formula_short_desc", "사용자 목표에 맞춘 맞춤형 조건식"),
        rules=[ConditionRule(**r) for r in rules],
        weights={},
        explanation_by_rule=llm.get("explanation_by_rule", {}),
        indicator_help={**DEFAULT_INDICATOR_HELP, **llm.get("indicator_help", {})},
        theme_hint=llm.get("theme_hint"),
    )

    # 설명 누락 시 기본값 채움
    for r in rec.rules:
        if r.key not in rec.explanation_by_rule:
            rec.explanation_by_rule[r.key] = f"{COND_KEYS.get(r.key, r.key)} 기준으로 종목의 특성을 평가해요."

    return rec


@app.get("/api/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/api/recommend", response_model=RecommendResponse)
def recommend(intent: UserIntent) -> RecommendResponse:
    if not intent.market or not intent.goal or not intent.horizon:
        raise HTTPException(status_code=400, detail="market, goal, horizon은 필수입니다.")

    df = load_universe(DATA_PATH)
    # 시장 필터
    if intent.market != "ALL":
        df = df[df["market"] == intent.market].copy()

    rules = pick_rules_by_intent(intent.goal, intent.horizon)
    rules = fill_rule_params(df, rules, intent.horizon)
    rec = _build_recommendation(intent, rules)

    df_scored, _sub = score_conditions(df, [r.dict() for r in rec.rules], rec.weights)
    theme_score = score_theme(df_scored, intent.theme)
    ranked = build_ranked(df_scored, theme_score)

    note = None
    mask = build_pass_mask(ranked, [r.dict() for r in rec.rules])
    filtered = ranked[mask].copy()
    if len(filtered) == 0:
        note = "조건을 모두 만족하는 종목이 적어 점수 기반으로 상위 종목을 표시합니다."
        filtered = ranked.copy()

    top_rows = filtered.head(10)

    # 기존 테마 요약(태그 기반)
    theme_briefs = _summarize_theme(
        intent,
        [
            {
                "symbol": str(r["symbol"]),
                "name": str(r["name"]),
                "tags": [t for t in str(r.get("tags", "")).split("|") if t],
            }
            for _, r in top_rows.iterrows()
        ],
    )
    top: List[RankedStock] = []
    for _, row in top_rows.iterrows():
        name = str(row["name"])
        symbol = str(row["symbol"])
        query_parts = [name, symbol]
        if intent.theme:
            query_parts.append(intent.theme)
        news_query = " ".join(query_parts)
        news_items = _fetch_news(news_query, lang="ko", max_items=3)
        news_summary = _summarize_news(news_items, name, intent.theme)

        top.append(
            RankedStock(
                symbol=symbol,
                name=name,
                market=str(row["market"]),
                condition_score=float(row["condition_score"]),
                theme_score=float(row["theme_score"]),
                total_score=float(row["total_score"]),
                why=explain_row(row, rec.formula_name, intent.theme),
                tags=[t for t in str(row.get("tags", "")).split("|") if t],
                rule_breakdown=build_rule_breakdown(row, [r.dict() for r in rec.rules]),
                theme_brief=news_summary or theme_briefs.get(symbol),
                news_items=news_items,
            )
        )

    return RecommendResponse(
        intent=intent,
        recommendation=rec,
        top=top,
        as_of=date.today().isoformat(),
        note=note,
    )
