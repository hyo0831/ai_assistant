# paturn.py
# -*- coding: utf-8 -*-
"""
패턴 분석 사용자정의 함수 모음

패턴 번호:
1) Cup & Handle
2) Double Bottom

- yfinance MultiIndex/Series ambiguity 방지: _get_series(...).squeeze()
- main.py에서 PATTERN_REGISTRY를 통해 패턴 선택 실행
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple, Callable

import numpy as np
import pandas as pd
import yfinance as yf


# =========================
# 공통 유틸
# =========================
def _get_series(df: pd.DataFrame, col: str) -> pd.Series:
    s = df[col]
    if isinstance(s, pd.DataFrame):
        s = s.iloc[:, 0]
    return s.squeeze()


def safe_download_yf(ticker: str, start, end) -> Optional[pd.DataFrame]:
    """
    yfinance 다운로드 안전 래퍼 (실패/빈값 방어)
    """
    try:
        df = yf.download(
            ticker,
            start=start,
            end=end,
            auto_adjust=False,
            progress=False,
        )
        if df is None or df.empty:
            return None
        return df
    except Exception:
        return None


def find_peaks_troughs(series: pd.Series) -> Tuple[List[pd.Timestamp], List[pd.Timestamp]]:
    peaks = (series.shift(1) < series) & (series.shift(-1) < series)
    troughs = (series.shift(1) > series) & (series.shift(-1) > series)
    return series[peaks].index.tolist(), series[troughs].index.tolist()


# =========================
# ===PATTERN=== 1
# Cup & Handle
# =========================
def _detect_cup(
    df: pd.DataFrame,
    min_cup_duration_weeks: int = 7,
    min_depth_percent: float = 15.0,
    max_depth_percent: float = 33.0,
) -> Optional[Dict]:
    close = _get_series(df, "Close")
    peaks, troughs = find_peaks_troughs(close)
    if len(peaks) < 2 or len(troughs) < 1:
        return None

    min_days = min_cup_duration_weeks * 5

    for i in range(len(peaks) - 1):
        left_idx = peaks[i]
        trough_candidates = [t for t in troughs if t > left_idx]
        if not trough_candidates:
            continue

        for bottom_idx in trough_candidates:
            right_candidates = [p for p in peaks if p > bottom_idx]
            if not right_candidates:
                continue

            for right_idx in right_candidates:
                dur = (right_idx - left_idx).days
                if dur < min_days:
                    continue

                left_p = float(close.loc[left_idx])
                right_p = float(close.loc[right_idx])
                bottom_p = float(close.loc[bottom_idx])

                # 립 가격 유사(±5%)
                if not (0.95 * left_p <= right_p <= 1.05 * left_p):
                    continue

                peak_p = max(left_p, right_p)
                depth = ((peak_p - bottom_p) / peak_p) * 100.0

                if min_depth_percent <= depth <= max_depth_percent:
                    seg = close.loc[left_idx:right_idx]
                    if float(bottom_p) == float(seg.min()):
                        return {
                            "left_lip_idx": left_idx,
                            "right_lip_idx": right_idx,
                            "bottom_idx": bottom_idx,
                            "depth_percent": float(depth),
                            "left_lip_price": float(left_p),
                            "right_lip_price": float(right_p),
                            "bottom_price": float(bottom_p),
                        }
    return None


def _detect_handle(
    df: pd.DataFrame,
    cup: Dict,
    max_handle_retracement_percent: float = 10.0,
    min_handle_retracement_percent: float = 5.0,
) -> Optional[Dict]:
    close = _get_series(df, "Close")
    right_idx = cup["right_lip_idx"]
    right_p = float(cup["right_lip_price"])

    start_pos = df.index.get_loc(right_idx) + 1
    if start_pos >= len(df):
        return None

    end_pos = min(start_pos + 20, len(df))
    if end_pos <= start_pos:
        return None

    seg = close.iloc[start_pos:end_pos]
    if seg.empty:
        return None

    h_high = float(seg.max())
    h_low = float(seg.min())

    if h_high > right_p:
        return None

    retr = ((right_p - h_low) / right_p) * 100.0
    if not (min_handle_retracement_percent <= retr <= max_handle_retracement_percent):
        return None

    fluct = ((h_high - h_low) / right_p) * 100.0
    if fluct > 10.0:
        return None

    return {
        "start_idx": seg.index[0],
        "end_idx": seg.index[-1],
        "handle_high": h_high,
        "handle_low": h_low,
        "retracement_percent": float(retr),
    }


def _confidence_cup_handle(df: pd.DataFrame, cup: Dict, handle: Dict) -> int:
    conf = 0

    depth = float(cup["depth_percent"])
    if 15 <= depth <= 25:
        conf += 40
    elif 10 <= depth < 15 or 25 < depth <= 33:
        conf += 20

    cup_days = len(df.loc[cup["left_lip_idx"] : cup["right_lip_idx"]])
    if cup_days >= 50:
        conf += 30
    elif cup_days >= 35:
        conf += 15

    vol = _get_series(df, "Volume")
    vseg = vol.loc[cup["left_lip_idx"] : cup["bottom_idx"]]
    if not vseg.empty:
        a = vseg.iloc[: len(vseg) // 2].mean()
        b = vseg.iloc[len(vseg) // 2 :].mean()
        if a > b * 1.2:
            conf += 15

    retr = float(handle["retracement_percent"])
    if 5 <= retr <= 8:
        conf += 10

    hv = vol.loc[handle["start_idx"] : handle["end_idx"]]
    if not hv.empty and len(hv) > 2:
        h_avg = hv.mean()
        last_avg = hv.iloc[-min(5, len(hv)) :].mean()
        if last_avg > h_avg * 1.15:
            conf += 5
        elif last_avg > h_avg * 0.95:
            conf += 2

    return min(int(conf), 100)


def pattern_01_cup_and_handle(name: str, ticker: str, df: pd.DataFrame) -> Optional[Dict]:
    """
    패턴 #1: Cup & Handle
    """
    if df is None or df.empty or len(df) < 120:
        return None

    cup = _detect_cup(df)
    if cup is None:
        return None

    handle = _detect_handle(df, cup)
    if handle is None:
        return None

    conf = _confidence_cup_handle(df, cup, handle)
    close = _get_series(df, "Close")
    cur = float(close.iloc[-1])

    pivot = float(cup["right_lip_price"])
    tp = pivot + (pivot - float(cup["bottom_price"]))
    sl = float(handle["handle_low"]) * 0.95

    labels = {
        "Cup Left": (cup["left_lip_idx"], cup["left_lip_price"]),
        "Cup Right": (cup["right_lip_idx"], cup["right_lip_price"]),
        "Cup Bottom": (cup["bottom_idx"], cup["bottom_price"]),
        "Handle S": (handle["start_idx"], float(close.loc[handle["start_idx"]])),
        "Handle E": (handle["end_idx"], float(close.loc[handle["end_idx"]])),
    }

    return {
        "pattern_no": 1,
        "pattern_name": "Cup & Handle",
        "name": name,
        "ticker": ticker,
        "confidence": conf,
        "current_price": cur,
        "pivot_price": float(pivot),
        "take_profit_price": float(tp),
        "stop_loss_price": float(sl),
        "data": df,
        "labels": labels,
    }


# =========================
# ===PATTERN=== 2
# Double Bottom
# =========================
def pattern_02_double_bottom(
    name: str,
    ticker: str,
    df: pd.DataFrame,
    lookback_days: int = 160,
    min_sep_days: int = 10,
    max_sep_days: int = 80,
    bottom_similarity_pct: float = 6.0,
    neckline_strength_pct: float = 8.0,
) -> Optional[Dict]:
    """
    패턴 #2: Double Bottom (간단하지만 쓸만한 최소 기준)
    """
    if df is None or df.empty or len(df) < 120:
        return None

    close = _get_series(df, "Close")
    seg = close.iloc[-lookback_days:] if len(close) > lookback_days else close.copy()

    peaks, troughs = find_peaks_troughs(seg)
    if len(troughs) < 2:
        return None

    troughs_sorted = sorted(troughs)
    best: Optional[Dict] = None
    best_conf = -1

    for i in range(len(troughs_sorted) - 1):
        for j in range(i + 1, len(troughs_sorted)):
            t1, t2 = troughs_sorted[i], troughs_sorted[j]
            sep = (t2 - t1).days
            if sep < min_sep_days or sep > max_sep_days:
                continue

            p1 = float(seg.loc[t1])
            p2 = float(seg.loc[t2])
            avg_bottom = (p1 + p2) / 2.0

            sim = abs(p2 - p1) / avg_bottom * 100.0
            if sim > bottom_similarity_pct:
                continue

            mid = seg.loc[t1:t2]
            if mid.empty:
                continue

            neckline_idx = mid.idxmax()
            neckline_price = float(mid.max())

            strength = (neckline_price - avg_bottom) / avg_bottom * 100.0
            if strength < neckline_strength_pct:
                continue

            cur = float(close.iloc[-1])

            conf = 0.0
            conf += max(0.0, 40.0 - sim * 4.0)
            conf += min(30.0, strength * 1.2)

            dist = (cur - neckline_price) / neckline_price * 100.0
            if dist >= 0:
                conf += 25.0
            else:
                conf += max(0.0, 25.0 + dist)

            conf_i = int(min(max(conf, 0.0), 100.0))

            if conf_i > best_conf:
                pivot = neckline_price
                tp = neckline_price + (neckline_price - avg_bottom)
                sl = avg_bottom * 0.97

                labels = {
                    "Bottom 1": (t1, p1),
                    "Bottom 2": (t2, p2),
                    "Neckline": (neckline_idx, neckline_price),
                }

                best = {
                    "pattern_no": 2,
                    "pattern_name": "Double Bottom",
                    "name": name,
                    "ticker": ticker,
                    "confidence": conf_i,
                    "current_price": cur,
                    "pivot_price": float(pivot),
                    "take_profit_price": float(tp),
                    "stop_loss_price": float(sl),
                    "data": df,
                    "labels": labels,
                }
                best_conf = conf_i

    return best


# =========================
# 패턴 레지스트리
# =========================
PATTERN_REGISTRY: Dict[int, Callable[[str, str, pd.DataFrame], Optional[Dict]]] = {
    1: pattern_01_cup_and_handle,
    2: pattern_02_double_bottom,
}
