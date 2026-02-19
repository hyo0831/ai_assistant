"""
바이낸스(Binance) Spot 클라이언트
- GET /api/v3/myTrades  (심볼별 조회)
- 사용자가 입력한 심볼 목록을 순회하여 체결 내역 수집
반환 포맷: 표준 레코드 리스트
"""

import hmac
import hashlib
import time
import requests
from datetime import datetime, timedelta
from urllib.parse import urlencode


BASE_URL = "https://api.binance.com"


class BinanceClient:
    def __init__(self, api_key: str, api_secret: str, symbols: list):
        self.api_key    = api_key
        self.api_secret = api_secret
        # symbols: ["BTCUSDT", "ETHUSDT", ...]
        self.symbols    = [s.upper().strip() for s in symbols if s.strip()]

    def _sign(self, params: dict) -> str:
        query = urlencode(params)
        return hmac.new(
            self.api_secret.encode(), query.encode(), hashlib.sha256
        ).hexdigest()

    def _get(self, path: str, params: dict) -> dict | list:
        params["timestamp"] = int(time.time() * 1000)
        params["signature"] = self._sign(params)
        headers = {"X-MBX-APIKEY": self.api_key}
        r = requests.get(f"{BASE_URL}{path}", headers=headers, params=params, timeout=10)
        r.raise_for_status()
        return r.json()

    def authenticate(self):
        """계좌 조회로 인증 확인"""
        try:
            self._get("/api/v3/account", {"recvWindow": 5000})
            print("  ✓ 바이낸스 인증 완료")
        except Exception as e:
            raise RuntimeError(f"바이낸스 인증 실패: {e}")

    def get_trade_history(self, days: int = 180) -> list:
        if not self.symbols:
            print("  [경고] 조회할 심볼이 없습니다.")
            return []

        cutoff_ms = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
        all_records = []

        for symbol in self.symbols:
            print(f"  [{symbol}] 체결 내역 조회 중...")
            trades = self._get("/api/v3/myTrades", {
                "symbol":     symbol,
                "startTime":  cutoff_ms,
                "limit":      1000,
                "recvWindow": 5000,
            })
            if isinstance(trades, list):
                for t in trades:
                    all_records.append(self._normalize(t, symbol))

        print(f"  ✓ 총 {len(all_records)}건 체결 내역 수집 ({len(self.symbols)}개 심볼)")
        return all_records

    @staticmethod
    def _normalize(t: dict, symbol: str) -> dict:
        ts  = int(t.get("time", 0))
        dt  = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M:%S") if ts else ""
        qty = float(t.get("qty", 0))
        price = float(t.get("price", 0))

        # 바이낸스 myTrades: isBuyer=True → 매수
        is_buyer = t.get("isBuyer", False)

        # 통화 추정: BTCUSDT → USDT, BTCBUSD → BUSD, BTCBTC → BTC
        currency = "USDT"
        for suffix in ("USDT", "BUSD", "BTC", "ETH", "BNB", "EUR", "USD"):
            if symbol.endswith(suffix):
                currency = suffix
                ticker   = symbol[: -len(suffix)]
                break
        else:
            ticker = symbol

        return {
            "dt":       dt,
            "side":     "buy" if is_buyer else "sell",
            "ticker":   ticker,
            "name":     ticker,
            "qty":      qty,
            "price":    price,
            "amount":   qty * price,
            "currency": currency,
        }
