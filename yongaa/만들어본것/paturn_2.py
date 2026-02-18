# paturn_2.py
# -*- coding: utf-8 -*-
"""
YOLO(이미지 기반) + 가격 기반 레벨 계산(피벗/TP/SL) 혼합 버전

요구 반영
- 패턴 감지 로직: rule-based -> YOLO 이미지 탐지로 전환
- TP/SL/Pivot은 '이미지'만으로는 점을 알기 어려워서,
  YOLO로 "해당 패턴 가능성"을 먼저 걸러낸 뒤, 기존 가격기반 휴리스틱으로 레벨을 계산함.
- main_2.py에서 candlestick 렌더링 + YOLO 추론에 사용 가능한 이미지 생성 함수 제공

패턴 번호:
1) Cup & Handle
2) Double Bottom

필수 설치(venv 안에서):
pip install ultralytics==8.* huggingface_hub opencv-python numpy pandas yfinance matplotlib
"""

from __future__ import annotations

import os
import tempfile
from typing import Dict, List, Optional, Tuple, Callable

import numpy as np
import pandas as pd
import yfinance as yf

# -------------------------
# yfinance MultiIndex 방지
# -------------------------
def _get_series(df: pd.DataFrame, col: str) -> pd.Series:
    s = df[col]
    if isinstance(s, pd.DataFrame):
        s = s.iloc[:, 0]
    return s.squeeze()

def safe_download_yf(ticker: str, start, end) -> Optional[pd.DataFrame]:
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


# =========================
# ===YOLO===
# =========================
_YOLO_MODEL = None
_YOLO_LABEL_MAP = {
    1: ["cup_and_handle", "cup-and-handle", "cupandhandle", "CupAndHandle", "Cup & Handle", "cup handle"],
    2: ["double_bottom", "double-bottom", "doublebottom", "DoubleBottom", "Double Bottom"],
}

def ensure_yolo_model(weights_path: Optional[str] = None, repo_id: str = "foduucom/stockmarket-pattern-detection-yolov8",
                      filename: str = "model.pt"):
    """
    YOLO 모델 로더
    - weights_path를 직접 주면 그걸 사용
    - 없으면 huggingface_hub로 다운로드 시도
    """
    global _YOLO_MODEL
    if _YOLO_MODEL is not None:
        return _YOLO_MODEL

    try:
        from ultralytics import YOLO
    except Exception as e:
        raise RuntimeError(
            "ultralytics가 설치되어야 해. venv 활성화 후:\n"
            "pip install ultralytics==8.*\n"
            f"(원인: {e})"
        )

    if weights_path and os.path.exists(weights_path):
        _YOLO_MODEL = YOLO(weights_path)
        return _YOLO_MODEL

    # HF 다운로드 시도
    try:
        from huggingface_hub import hf_hub_download
        weights_path = hf_hub_download(repo_id=repo_id, filename=filename)
        _YOLO_MODEL = YOLO(weights_path)
        return _YOLO_MODEL
    except Exception as e:
        raise RuntimeError(
            "YOLO weight(model.pt)를 로드/다운로드하지 못했어.\n"
            "1) huggingface_hub 설치 확인: pip install huggingface_hub\n"
            "2) 네트워크/권한 확인\n"
            "3) 또는 weights_path로 로컬 model.pt 경로를 직접 넘겨줘.\n"
            f"(원인: {e})"
        )


def yolo_predict_on_image(image_path: str, conf: float = 0.25, iou: float = 0.45) -> List[Dict]:
    """
    이미지 1장에 대해 YOLO 예측 결과를 list[dict]로 변환
    """
    model = ensure_yolo_model()
    results = model.predict(source=image_path, imgsz=640, conf=conf, iou=iou, verbose=False)
    r = results[0]

    preds = []
    for box in r.boxes:
        cls_id = int(box.cls[0])
        label = r.names.get(cls_id, str(cls_id))
        conf_v = float(box.conf[0])
        xyxy = box.xyxy[0].tolist()  # [x1,y1,x2,y2]
        preds.append({"label": label, "confidence": conf_v, "xyxy": xyxy})
    return preds


def pick_best_label(preds: List[Dict], pattern_no: int) -> Optional[Dict]:
    """
    특정 패턴 번호에 해당하는 label 후보들 중 confidence 최고 1개 선택
    """
    targets = set([s.lower() for s in _YOLO_LABEL_MAP.get(pattern_no, [])])
    best = None
    best_c = -1.0
    for p in preds:
        lab = str(p["label"]).lower()
        if lab in targets:
            if p["confidence"] > best_c:
                best = p
                best_c = p["confidence"]
    return best


# =========================
# ===차트 이미지 생성(캔들)===
# =========================
def render_candles_to_image(df: pd.DataFrame, title: str = "", out_path: Optional[str] = None,
                            max_bars: int = 180) -> str:
    """
    OHLCV -> 캔들스틱 이미지를 생성해서 파일 경로를 반환
    - ultralytics 입력용(파일 경로 필요)
    """
    import matplotlib
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    data = df.copy()
    if len(data) > max_bars:
        data = data.iloc[-max_bars:]

    o = _get_series(data, "Open")
    h = _get_series(data, "High")
    l = _get_series(data, "Low")
    c = _get_series(data, "Close")

    x = np.arange(len(data))

    fig, ax = plt.subplots(figsize=(8.5, 5.5), dpi=120)
    ax.set_title(title, fontsize=11)
    ax.grid(True, alpha=0.2)

    # 캔들폭
    width = 0.6

    for i in range(len(data)):
        # wick
        ax.vlines(x[i], l.iloc[i], h.iloc[i], linewidth=1)

        # body
        open_p = float(o.iloc[i])
        close_p = float(c.iloc[i])
        lower = min(open_p, close_p)
        height = abs(close_p - open_p)
        if height == 0:
            height = (float(h.iloc[i]) - float(l.iloc[i])) * 0.01  # 아주 작은 몸통

        rect = Rectangle((x[i] - width/2, lower), width, height)
        ax.add_patch(rect)

    ax.set_xlim(-1, len(data))
    ax.set_xticks([0, len(data)//2, len(data)-1])
    ax.set_xticklabels([data.index[0].strftime("%Y-%m-%d"),
                        data.index[len(data)//2].strftime("%Y-%m-%d"),
                        data.index[-1].strftime("%Y-%m-%d")], rotation=0)

    ax.set_ylabel("Price")

    # 저장
    if out_path is None:
        fd, out_path = tempfile.mkstemp(suffix=".png")
        os.close(fd)

    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    return out_path


# =========================
# ===레벨 계산(가격 기반 휴리스틱)===
# =========================
def find_peaks_troughs(series: pd.Series) -> Tuple[List[pd.Timestamp], List[pd.Timestamp]]:
    peaks = (series.shift(1) < series) & (series.shift(-1) < series)
    troughs = (series.shift(1) > series) & (series.shift(-1) > series)
    return series[peaks].index.tolist(), series[troughs].index.tolist()


def _calc_levels_cup_handle(df: pd.DataFrame) -> Optional[Dict]:
    """
    기존 휴리스틱(간단/안정)으로 컵앤핸들 레벨 계산
    - 엄격 탐지는 YOLO가 담당
    - 여기서는 Pivot/TP/SL과 라벨용 key points를 잡음
    """
    close = _get_series(df, "Close")
    peaks, troughs = find_peaks_troughs(close)
    if len(peaks) < 2 or len(troughs) < 1:
        return None

    # 최근 구간에서 "비슷한 피크 2개"를 찾되, 너무 과하게 탐색하지 않음
    # 오른쪽 립 후보를 최근 피크들부터 탐색
    peaks_sorted = sorted(peaks)
    troughs_sorted = sorted(troughs)

    # 최근 6개월 정도만 기준(대략 120일)
    window = 160
    seg = close.iloc[-window:] if len(close) > window else close
    peaks2, troughs2 = find_peaks_troughs(seg)
    if len(peaks2) < 2 or len(troughs2) < 1:
        return None

    peaks2 = sorted(peaks2)
    troughs2 = sorted(troughs2)

    best = None
    best_depth = -1.0

    for i in range(len(peaks2)-1):
        left = peaks2[i]
        # left 이후 trough
        cand_tr = [t for t in troughs2 if t > left]
        if not cand_tr:
            continue
        for bottom in cand_tr:
            cand_r = [p for p in peaks2 if p > bottom]
            if not cand_r:
                continue
            for right in cand_r:
                left_p = float(seg.loc[left])
                right_p = float(seg.loc[right])
                bottom_p = float(seg.loc[bottom])

                # 립 유사 ±8% (YOLO가 이미 거른 상태라 약간 느슨하게)
                if not (0.92 * left_p <= right_p <= 1.08 * left_p):
                    continue

                peak_p = max(left_p, right_p)
                depth = (peak_p - bottom_p) / peak_p * 100.0
                if depth < 8 or depth > 45:
                    continue

                if depth > best_depth:
                    best_depth = depth
                    best = (left, bottom, right, left_p, bottom_p, right_p)

    if not best:
        return None

    left, bottom, right, left_p, bottom_p, right_p = best
    pivot = right_p
    tp = pivot + (pivot - bottom_p)
    sl = bottom_p * 0.97

    labels = {
        "Cup Left": (left, left_p),
        "Cup Bottom": (bottom, bottom_p),
        "Cup Right": (right, right_p),
    }

    return {"pivot": float(pivot), "tp": float(tp), "sl": float(sl), "labels": labels}


def _calc_levels_double_bottom(df: pd.DataFrame) -> Optional[Dict]:
    close = _get_series(df, "Close")
    seg = close.iloc[-200:] if len(close) > 200 else close
    peaks, troughs = find_peaks_troughs(seg)
    if len(troughs) < 2:
        return None

    troughs = sorted(troughs)
    best = None
    best_strength = -1.0

    for i in range(len(troughs)-1):
        b1, b2 = troughs[i], troughs[i+1]
        sep = (b2 - b1).days
        if sep < 7 or sep > 120:
            continue
        p1 = float(seg.loc[b1])
        p2 = float(seg.loc[b2])
        avg_bottom = (p1 + p2) / 2.0
        sim = abs(p2 - p1) / avg_bottom * 100.0
        if sim > 8.0:
            continue

        mid = seg.loc[b1:b2]
        if mid.empty:
            continue
        neckline_idx = mid.idxmax()
        neckline = float(mid.max())
        strength = (neckline - avg_bottom) / avg_bottom * 100.0
        if strength < 6.0:
            continue

        if strength > best_strength:
            best_strength = strength
            best = (b1, b2, neckline_idx, p1, p2, neckline)

    if not best:
        return None

    b1, b2, nk_i, p1, p2, neckline = best
    avg_bottom = (p1 + p2) / 2.0
    pivot = neckline
    tp = pivot + (pivot - avg_bottom)
    sl = avg_bottom * 0.97

    labels = {
        "Bottom 1": (b1, p1),
        "Bottom 2": (b2, p2),
        "Neckline": (nk_i, neckline),
    }
    return {"pivot": float(pivot), "tp": float(tp), "sl": float(sl), "labels": labels}


# =========================
# ===PATTERN=== 1/2 (YOLO 기반 감지)
# =========================
def pattern_01_cup_and_handle(name: str, ticker: str, df: pd.DataFrame, yolo_conf: float = 0.25) -> Optional[Dict]:
    if df is None or df.empty or len(df) < 80:
        return None

    # 1) 캔들 이미지 생성 -> 2) YOLO 예측 -> 3) 레벨 계산
    img = render_candles_to_image(df, title=f"{name} {ticker} (Candles)")
    try:
        preds = yolo_predict_on_image(img, conf=yolo_conf, iou=0.45)
    finally:
        try:
            os.remove(img)
        except Exception:
            pass

    best = pick_best_label(preds, 1)
    if not best:
        return None

    levels = _calc_levels_cup_handle(df)
    if not levels:
        return None

    close = _get_series(df, "Close")
    cur = float(close.iloc[-1])

    return {
        "pattern_no": 1,
        "pattern_name": "Cup & Handle (YOLO)",
        "name": name,
        "ticker": ticker,
        "confidence": int(min(max(best["confidence"] * 100.0, 0.0), 100.0)),
        "current_price": cur,
        "pivot_price": levels["pivot"],
        "take_profit_price": levels["tp"],
        "stop_loss_price": levels["sl"],
        "data": df,
        "labels": levels["labels"],
        "yolo_label": best["label"],
        "yolo_conf": float(best["confidence"]),
    }


def pattern_02_double_bottom(name: str, ticker: str, df: pd.DataFrame, yolo_conf: float = 0.25) -> Optional[Dict]:
    if df is None or df.empty or len(df) < 80:
        return None

    img = render_candles_to_image(df, title=f"{name} {ticker} (Candles)")
    try:
        preds = yolo_predict_on_image(img, conf=yolo_conf, iou=0.45)
    finally:
        try:
            os.remove(img)
        except Exception:
            pass

    best = pick_best_label(preds, 2)
    if not best:
        return None

    levels = _calc_levels_double_bottom(df)
    if not levels:
        return None

    close = _get_series(df, "Close")
    cur = float(close.iloc[-1])

    return {
        "pattern_no": 2,
        "pattern_name": "Double Bottom (YOLO)",
        "name": name,
        "ticker": ticker,
        "confidence": int(min(max(best["confidence"] * 100.0, 0.0), 100.0)),
        "current_price": cur,
        "pivot_price": levels["pivot"],
        "take_profit_price": levels["tp"],
        "stop_loss_price": levels["sl"],
        "data": df,
        "labels": levels["labels"],
        "yolo_label": best["label"],
        "yolo_conf": float(best["confidence"]),
    }


# =========================
# 레지스트리
# =========================
PATTERN_REGISTRY: Dict[int, Callable[..., Optional[Dict]]] = {
    1: pattern_01_cup_and_handle,
    2: pattern_02_double_bottom,
}
