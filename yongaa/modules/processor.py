"""
시장별 매매 지표 산출
입력: 표준 레코드 리스트 (각 클라이언트가 normalize 완료)
출력: metrics dict

표준 레코드 필드:
  dt       : "YYYY-MM-DD HH:MM:SS"
  side     : "buy" | "sell"
  ticker   : str
  name     : str (optional)
  qty      : float
  price    : float  (체결 평균가)
  amount   : float  (qty * price)
  currency : str    ("KRW", "USD", "USDT", ...)
"""

import pandas as pd
from datetime import datetime


def process_trades(records: list, market_type: str) -> dict:
    """
    FIFO 매칭으로 완결된 매매를 페어링하고 지표를 산출한다.
    market_type: "korean" | "abroad" | "coin"
    """
    if not records:
        return {"error": "체결 내역 없음", "total_trades": 0}

    df = pd.DataFrame(records)

    # datetime 파싱
    df["datetime"] = pd.to_datetime(df["dt"], errors="coerce")

    # 수치형 변환 (이미 float이어야 하지만 안전하게 처리)
    for col in ["qty", "price", "amount"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    currency = df["currency"].iloc[0] if "currency" in df.columns else "KRW"

    # ── FIFO 매매 페어링 ──────────────────────────────────────────
    completed      = []
    martingale_cnt = 0

    for ticker, grp in df.groupby("ticker"):
        grp = grp.sort_values("datetime").reset_index(drop=True)
        buy_queue  = []   # {"qty": float, "price": float, "dt": datetime}
        consec_buy = 0

        for _, row in grp.iterrows():
            side  = str(row.get("side", ""))
            qty   = float(row.get("qty",   0))
            price = float(row.get("price", 0))
            dt    = row.get("datetime")

            if side == "buy":
                buy_queue.append({"qty": qty, "price": price, "dt": dt})
                consec_buy += 1
                if consec_buy > 1:
                    martingale_cnt += 1  # 연속 매수 → 물타기 의심

            elif side == "sell" and buy_queue:
                consec_buy = 0
                remain = qty
                while remain > 0 and buy_queue:
                    b       = buy_queue[0]
                    matched = min(remain, b["qty"])
                    pnl     = (price - b["price"]) * matched
                    pnl_pct = (price - b["price"]) / b["price"] * 100 if b["price"] else 0
                    hold_h  = (
                        (dt - b["dt"]).total_seconds() / 3600
                        if pd.notnull(dt) and pd.notnull(b["dt"]) else None
                    )
                    completed.append({
                        "ticker":        ticker,
                        "buy_price":     b["price"],
                        "sell_price":    price,
                        "qty":           matched,
                        "pnl":           pnl,
                        "pnl_pct":       pnl_pct,
                        "holding_hours": hold_h,
                        "win":           pnl > 0,
                    })
                    b["qty"] -= matched
                    remain   -= matched
                    if b["qty"] <= 0:
                        buy_queue.pop(0)

    if not completed:
        return {
            "error":      "완결된 매매 없음 (미청산 포지션만 존재 또는 데이터 부족)",
            "total_trades": 0,
            "raw_count":  len(df),
            "currency":   currency,
        }

    tdf  = pd.DataFrame(completed)
    tot  = len(tdf)
    wins = int(tdf["win"].sum())
    loss = tot - wins

    avg_profit = tdf.loc[tdf["win"],  "pnl_pct"].mean() if wins else 0.0
    avg_loss   = abs(tdf.loc[~tdf["win"], "pnl_pct"].mean()) if loss else 0.0
    rr_ratio   = round(avg_profit / avg_loss, 2) if avg_loss else 99.99

    # MDD (누적 손익 기준)
    tdf["cum_pnl"]  = tdf["pnl"].cumsum()
    tdf["peak"]     = tdf["cum_pnl"].cummax()
    tdf["drawdown"] = tdf["cum_pnl"] - tdf["peak"]
    mdd             = tdf["drawdown"].min()

    avg_hold = tdf["holding_hours"].dropna().mean()

    # 시장별 추가 지표
    extra = _market_extra(tdf, market_type)

    return {
        "market_type":      market_type,
        "currency":         currency,
        "total_trades":     tot,
        "win_trades":       wins,
        "loss_trades":      loss,
        "win_rate":         round(wins / tot * 100, 1),
        "avg_profit_pct":   round(avg_profit, 2),
        "avg_loss_pct":     round(avg_loss, 2),
        "rr_ratio":         rr_ratio,
        "total_pnl":        round(tdf["pnl"].sum(), 2),
        "mdd":              round(mdd, 2),
        "avg_holding_hours": round(avg_hold, 1) if pd.notnull(avg_hold) else None,
        "martingale_count": martingale_cnt,
        **extra,
    }


def _market_extra(tdf: pd.DataFrame, market_type: str) -> dict:
    """시장별 추가 지표"""
    extra = {}

    if market_type == "coin":
        # 코인: 레버리지 여부 판단 불가 → holding_hours 분포로 스타일 추정
        h = tdf["holding_hours"].dropna()
        if not h.empty:
            scalp_pct = (h < 1).sum() / len(h) * 100   # 1시간 미만 = 단타
            swing_pct = (h > 24).sum() / len(h) * 100  # 24시간 초과 = 스윙
            extra["scalp_ratio_pct"] = round(scalp_pct, 1)
            extra["swing_ratio_pct"] = round(swing_pct, 1)

    elif market_type == "abroad":
        # 해외: 종목 다양성
        unique_tickers = tdf["ticker"].nunique() if "ticker" in tdf.columns else 0
        extra["unique_tickers"] = unique_tickers

    elif market_type == "korean":
        # 국내: 동일 종목 반복 매매 횟수 (테마 집중도)
        if "ticker" in tdf.columns:
            top_ticker = tdf["ticker"].value_counts().idxmax()
            top_count  = tdf["ticker"].value_counts().max()
            extra["most_traded_ticker"] = top_ticker
            extra["most_traded_count"]  = int(top_count)

    return extra
