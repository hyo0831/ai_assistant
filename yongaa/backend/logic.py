from __future__ import annotations
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from datetime import date

# 9가지 조건 키(고정)
COND_KEYS = {
    "volume": "거래량",
    "value": "거래대금",
    "foreign_own": "외국인소진율",
    "per_low": "저 PER",
    "pbr_low": "저 PBR",
    "roe_high": "고 ROE",
    "ma_cross": "이평선 크로스",
    "rsi_range": "RSI 범위",
    "obv": "OBV",
}

DEFAULT_INDICATOR_HELP = {
    "volume": "거래량은 시장의 관심도를 보여줘요. 높을수록 단타·스윙에 유리해요.",
    "value": "거래대금은 실제 자금 유입 규모를 뜻해요. 유동성 안정성을 확인할 때 봐요.",
    "foreign_own": "외국인 보유 비중은 중장기 수급 신호로 쓰여요.",
    "per_low": "PER이 낮을수록 이익 대비 가격이 싸다는 뜻이에요.",
    "pbr_low": "PBR은 자산가치 대비 가격 지표예요. 낮을수록 저평가로 봐요.",
    "roe_high": "ROE는 자본 대비 수익성을 뜻해요. 높을수록 효율이 좋아요.",
    "ma_cross": "단기-중기 이평선 골든/데드 크로스로 추세 전환을 봐요.",
    "rsi_range": "RSI는 과열/과매도 구간을 보여요. 목표 구간에서 안정적인 종목을 선호해요.",
    "obv": "OBV는 거래량 기반 수급 추세예요. 상승 기울기가 매수 우위예요.",
}

RULE_VALUE_FIELD = {
    "volume": "avg_volume_20",
    "value": "avg_value_20",
    "foreign_own": "foreign_own",
    "per_low": "per",
    "pbr_low": "pbr",
    "roe_high": "roe",
    "ma_cross": "ma_cross_score",
    "rsi_range": "rsi_14",
    "obv": "obv_slope",
}

def _q(series: pd.Series, q: float) -> float:
    try:
        return float(series.quantile(q))
    except Exception:
        return float(series.dropna().median()) if len(series) else 0.0

def fill_rule_params(df: pd.DataFrame, rules: List[dict], horizon: str) -> List[dict]:
    # 규칙별 수치 채우기 (데모: 분위수 기반, 실제 데이터로 교체 가능)
    volume_q = 0.8 if horizon == "day" else 0.6 if horizon == "swing" else 0.4
    value_q = 0.8 if horizon == "day" else 0.6 if horizon == "swing" else 0.4

    for r in rules:
        key = r["key"]
        if key == "volume":
            r["op"] = ">="
            r["value"] = _q(df["avg_volume_20"], volume_q)
            r.setdefault("meta", {})["basis"] = f"quantile_{volume_q}"
            r["meta"]["field"] = "avg_volume_20"
        elif key == "value":
            r["op"] = ">="
            r["value"] = _q(df["avg_value_20"], value_q)
            r.setdefault("meta", {})["basis"] = f"quantile_{value_q}"
            r["meta"]["field"] = "avg_value_20"
        elif key == "foreign_own":
            r["op"] = ">="
            r["value"] = _q(df["foreign_own"], 0.6)
        elif key == "per_low":
            r["op"] = "<="
            r["value"] = _q(df["per"], 0.3)
        elif key == "pbr_low":
            r["op"] = "<="
            r["value"] = _q(df["pbr"], 0.3)
        elif key == "roe_high":
            r["op"] = ">="
            r["value"] = _q(df["roe"], 0.7)
        elif key == "ma_cross":
            r["op"] = "cross"
            r.setdefault("meta", {})["type"] = "golden"
            r["meta"]["fast"] = "5"
            r["meta"]["slow"] = "20"
        elif key == "rsi_range":
            r["op"] = "between"
            if horizon == "day":
                r["min"], r["max"] = 50, 70
            elif horizon == "swing":
                r["min"], r["max"] = 40, 65
            else:
                r["min"], r["max"] = 30, 60
        elif key == "obv":
            r["op"] = ">="
            r["value"] = _q(df["obv_slope"], 0.6)
    return rules

def rule_pass(value: float, rule: dict) -> bool:
    op = rule.get("op")
    if op == ">=":
        return value >= float(rule.get("value", 0))
    if op == "<=":
        return value <= float(rule.get("value", 0))
    if op == "between":
        return float(rule.get("min", -1e9)) <= value <= float(rule.get("max", 1e9))
    if op == "cross":
        # ma_cross_score가 0.6 이상이면 골든크로스 유사 신호로 처리
        return value >= 0.6
    return True

def build_pass_mask(df: pd.DataFrame, rules: List[dict]) -> pd.Series:
    mask = pd.Series(True, index=df.index)
    for r in rules:
        key = r["key"]
        field = RULE_VALUE_FIELD.get(key)
        if not field or field not in df.columns:
            continue
        v = df[field].fillna(0.0)
        mask = mask & v.apply(lambda x: rule_pass(float(x), r))
    return mask

def build_rule_breakdown(row: pd.Series, rules: List[dict]) -> Dict[str, Dict[str, object]]:
    out: Dict[str, Dict[str, object]] = {}
    for r in rules:
        key = r["key"]
        field = RULE_VALUE_FIELD.get(key)
        if not field or field not in row:
            continue
        value = float(row[field]) if row[field] == row[field] else 0.0
        passed = rule_pass(value, r)
        out[key] = {
            "value": value,
            "op": r.get("op"),
            "min": r.get("min"),
            "max": r.get("max"),
            "threshold": r.get("value"),
            "passed": passed,
        }
    return out

def load_universe(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    # 안전 처리
    df["tags"] = df["tags"].fillna("").astype(str)
    df["theme_tags"] = df["theme_tags"].fillna("").astype(str)
    return df


def clamp01(x: float) -> float:
    return float(max(0.0, min(1.0, x)))


def percentile_score(series: pd.Series, higher_better: bool = True) -> pd.Series:
    # 0~100 점수화 (퍼센타일 기반)
    rank = series.rank(pct=True, method="average")
    if not higher_better:
        rank = 1.0 - rank
    return (rank * 100.0).fillna(0.0)


def score_conditions(df: pd.DataFrame, picked_rules: List[dict], weights: Dict[str, float]) -> Tuple[pd.DataFrame, Dict[str, pd.Series]]:
    """
    picked_rules: [{key, op, value/min/max ...}]
    weights: {key: weight} 0~1 합 1 권장(아니어도 정규화함)
    """
    w = dict(weights or {})
    # 기본 가중치가 없으면 균등
    keys = [r["key"] for r in picked_rules]
    if not w:
        w = {k: 1.0 for k in keys}

    # 정규화
    s = sum(abs(v) for v in w.values()) or 1.0
    w = {k: float(v) / s for k, v in w.items()}

    sub_scores: Dict[str, pd.Series] = {}

    for rule in picked_rules:
        key = rule["key"]

        # 지표별 점수 계산 로직(샘플)
        if key == "volume":
            sub_scores[key] = percentile_score(df["avg_volume_20"], higher_better=True)
        elif key == "value":
            sub_scores[key] = percentile_score(df["avg_value_20"], higher_better=True)
        elif key == "foreign_own":
            sub_scores[key] = percentile_score(df["foreign_own"], higher_better=True)
        elif key == "per_low":
            sub_scores[key] = percentile_score(df["per"], higher_better=False)
        elif key == "pbr_low":
            sub_scores[key] = percentile_score(df["pbr"], higher_better=False)
        elif key == "roe_high":
            sub_scores[key] = percentile_score(df["roe"], higher_better=True)
        elif key == "ma_cross":
            # 샘플: ma_cross_score (0~1)
            sub_scores[key] = (df["ma_cross_score"].fillna(0.0) * 100.0).clip(0, 100)
        elif key == "rsi_range":
            # 50~70 같은 "모멘텀/과열 전" 구간 선호 예시: 목표 구간에 가까울수록 점수↑
            mn = float(rule.get("min", 40))
            mx = float(rule.get("max", 70))
            rsi = df["rsi_14"].fillna(0.0)

            # 구간 내부=100, 바깥은 거리 기반 감점
            dist = np.where(rsi < mn, mn - rsi, np.where(rsi > mx, rsi - mx, 0.0))
            # dist가 0이면 100, dist가 20이면 0 근처
            score = (100.0 - (dist / 20.0) * 100.0).clip(0, 100)
            sub_scores[key] = pd.Series(score, index=df.index)
        elif key == "obv":
            # 샘플: obv_slope (기울기) 높을수록 수급 우상향
            sub_scores[key] = percentile_score(df["obv_slope"], higher_better=True)
        else:
            sub_scores[key] = pd.Series(0.0, index=df.index)

    # 조건 종합점수
    condition_score = pd.Series(0.0, index=df.index)
    for k, sc in sub_scores.items():
        condition_score += sc * w.get(k, 0.0)

    out = df.copy()
    out["condition_score"] = condition_score.clip(0, 100)
    return out, sub_scores


def score_theme(df: pd.DataFrame, theme: str | None) -> pd.Series:
    if not theme:
        return pd.Series(50.0, index=df.index)  # 테마 미입력 시 중립값
    theme_l = theme.strip().lower()
    # 샘플: theme_tags에 포함되면 가산점
    tags = df["theme_tags"].str.lower()
    hit = tags.apply(lambda x: 1.0 if theme_l in x else 0.0)
    # 기본 40 + hit면 60 추가
    return (40.0 + hit * 60.0).clip(0, 100)


def build_ranked(df_scored: pd.DataFrame, theme_score: pd.Series) -> pd.DataFrame:
    out = df_scored.copy()
    out["theme_score"] = theme_score
    out["total_score"] = (out["condition_score"] * 0.7 + out["theme_score"] * 0.3).clip(0, 100)
    out = out.sort_values("total_score", ascending=False)
    return out


def explain_row(row: pd.Series, formula_name: str, theme: str | None) -> str:
    bits = []
    bits.append(f"{formula_name} 기준 종합점수가 높아요.")
    bits.append(f"조건점수 {row['condition_score']:.0f}점, 테마점수 {row['theme_score']:.0f}점.")
    if theme:
        if float(row["theme_score"]) >= 90:
            bits.append(f"테마 '{theme}' 연관 신호가 강한 편.")
        elif float(row["theme_score"]) <= 50:
            bits.append(f"테마 '{theme}' 직접 연관은 약한 편.")
    return " ".join(bits)


def pick_rules_by_intent(goal: str, horizon: str) -> List[dict]:
    g = (goal or "").lower()
    rules: List[dict] = []

    # 기본: 유동성 + 추세
    if any(x in g for x in ["단타", "스캘", "스윙", "모멘텀", "추세", "breakout", "돌파"]):
        rules += [
            {"id": 1, "key": "volume", "op": ">="},
            {"id": 2, "key": "value", "op": ">="},
            {"id": 7, "key": "ma_cross", "op": "cross"},
            {"id": 8, "key": "rsi_range", "op": "between", "min": 45, "max": 70},
        ]
    elif any(x in g for x in ["저평가", "가치", "마법", "퀀트", "우량", "long", "중장기"]):
        rules += [
            {"id": 4, "key": "per_low", "op": "<="},
            {"id": 5, "key": "pbr_low", "op": "<="},
            {"id": 6, "key": "roe_high", "op": ">="},
            {"id": 3, "key": "foreign_own", "op": ">="},
        ]
    else:
        rules += [
            {"id": 1, "key": "volume", "op": ">="},
            {"id": 4, "key": "per_low", "op": "<="},
            {"id": 6, "key": "roe_high", "op": ">="},
            {"id": 9, "key": "obv", "op": ">="},
        ]

    # 기간 보정
    if horizon == "day":
        rules = [r for r in rules if r["key"] in {"volume", "value", "ma_cross", "rsi_range", "obv"}]
        rules += [
            {"id": 1, "key": "volume", "op": ">="},
            {"id": 7, "key": "ma_cross", "op": "cross"},
            {"id": 8, "key": "rsi_range", "op": "between", "min": 50, "max": 70},
        ]
    elif horizon == "long":
        rules = [r for r in rules if r["key"] in {"per_low", "pbr_low", "roe_high", "foreign_own"}]
        rules += [
            {"id": 4, "key": "per_low", "op": "<="},
            {"id": 5, "key": "pbr_low", "op": "<="},
            {"id": 6, "key": "roe_high", "op": ">="},
        ]

    # 중복 제거
    seen = set()
    uniq = []
    for r in rules:
        if r["key"] in seen:
            continue
        seen.add(r["key"])
        uniq.append(r)
    return uniq[:5]


def default_formula_name(horizon: str, market: str) -> str:
    if horizon == "day":
        return f"{market} 초단타 유동성-추세식"
    if horizon == "swing":
        return f"{market} 스윙 모멘텀-퀄리티식"
    return f"{market} 장기 저평가-수익성식"
