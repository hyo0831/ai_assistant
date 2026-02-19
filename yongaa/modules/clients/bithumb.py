"""
빗썸(Bithumb) 클라이언트 (pybithumb 기반)
pip install pybithumb

KRW 마켓 주요 코인의 거래 내역을 수집한다.
반환: 표준 레코드 리스트
  {"dt", "side", "ticker", "name", "qty", "price", "amount", "currency"}
"""

from datetime import datetime, timedelta

# 기본 조회 대상 KRW 코인 목록 (사용자가 추가 가능)
DEFAULT_COINS = [
    "BTC", "ETH", "XRP", "SOL", "BNB",
    "DOGE", "ADA", "MATIC", "AVAX", "LINK",
]


class BithumbClient:
    def __init__(self, api_key: str, api_secret: str, coins: list | None = None):
        self.api_key    = api_key
        self.api_secret = api_secret
        self.coins      = coins or DEFAULT_COINS
        self._bt        = None

    def authenticate(self):
        try:
            import pybithumb
        except ImportError:
            raise ImportError("pybithumb 설치 필요: pip install pybithumb")

        self._bt = pybithumb.Bithumb(self.api_key, self.api_secret)

        # 잔고 조회로 인증 확인
        try:
            balance = self._bt.get_balance("BTC")
            if balance is None:
                raise RuntimeError("빗썸 인증 실패: API 키를 확인하세요.")
        except Exception as e:
            raise RuntimeError(f"빗썸 인증 오류: {e}")

        print("  ✓ 빗썸 인증 완료")

    def get_trade_history(self, days: int = 180) -> list:
        """KRW 마켓 코인별 거래 내역 수집"""
        cutoff   = datetime.now() - timedelta(days=days)
        all_recs = []

        for coin in self.coins:
            try:
                orders = self._bt.get_trading_history(coin)
                if orders is None:
                    continue
                recs = self._parse_orders(orders, coin, cutoff)
                if recs:
                    print(f"  [{coin}] {len(recs)}건")
                    all_recs.extend(recs)
            except Exception:
                pass  # 해당 코인 거래 없음 → 스킵

        print(f"  ✓ 총 {len(all_recs)}건 수집 (빗썸 {len(self.coins)}개 코인)")
        return all_recs

    def _parse_orders(self, orders, coin: str, cutoff: datetime) -> list:
        """pybithumb 반환값 파싱 → 표준 포맷"""
        records = []

        # pybithumb은 list[dict] 또는 DataFrame 반환
        items = []
        try:
            import pandas as pd
            if isinstance(orders, pd.DataFrame):
                items = orders.to_dict("records")
            else:
                items = list(orders) if orders else []
        except ImportError:
            items = list(orders) if orders else []

        for item in items:
            rec = self._normalize(item, coin, cutoff)
            if rec:
                records.append(rec)
        return records

    @staticmethod
    def _normalize(item: dict, coin: str, cutoff: datetime) -> dict | None:
        def g(*keys):
            for k in keys:
                v = str(item.get(k, "0")).replace(",", "").strip()
                try:
                    return float(v)
                except ValueError:
                    pass
            return 0.0

        # 날짜 파싱 (pybithumb 필드: transaction_date 또는 created_at)
        dt_raw = item.get("transaction_date", item.get("created_at", ""))
        try:
            dt = datetime.strptime(str(dt_raw)[:19], "%Y-%m-%d %H:%M:%S")
        except Exception:
            try:
                dt = datetime.strptime(str(dt_raw)[:19], "%Y-%m-%dT%H:%M:%S")
            except Exception:
                dt = datetime.now()

        if dt < cutoff:
            return None

        # pybithumb 체결 필드: type(bid/ask), units_traded, price
        side_raw = str(item.get("type", item.get("order_type", ""))).lower()
        side     = "buy" if side_raw in ("bid", "buy") else "sell"
        qty      = g("units_traded", "volume", "quantity")
        price    = g("price", "avg_price")
        amount   = g("total", "amount") or qty * price

        if qty <= 0 or price <= 0:
            return None

        return {
            "dt":       dt.strftime("%Y-%m-%d %H:%M:%S"),
            "side":     side,
            "ticker":   coin,
            "name":     coin,
            "qty":      qty,
            "price":    price,
            "amount":   amount,
            "currency": "KRW",
        }
