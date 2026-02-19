"""
업비트(Upbit) 클라이언트
- 완료된 주문(state=done) 전체 조회
- JWT 인증 (PyJWT 필요)
반환 포맷: 표준 레코드 리스트 (dt, side, ticker, qty, price, amount, currency)
"""

import uuid
import hashlib
import requests
from datetime import datetime, timedelta, timezone

try:
    import jwt as pyjwt
except ImportError:
    raise ImportError("PyJWT 패키지가 필요합니다: pip install PyJWT")


BASE_URL = "https://api.upbit.com"


class UpbitClient:
    def __init__(self, access_key: str, secret_key: str):
        self.access_key = access_key
        self.secret_key = secret_key

    def authenticate(self):
        """업비트는 매 요청마다 JWT를 생성하므로 별도 토큰 발급 불필요."""
        # 간단한 연결 테스트
        r = requests.get(f"{BASE_URL}/v1/accounts", headers=self._headers(), timeout=10)
        if r.status_code == 401:
            raise RuntimeError("업비트 인증 실패: Access Key / Secret Key를 확인하세요.")
        r.raise_for_status()
        print("  ✓ 업비트 인증 완료")

    def _headers(self, query_params: dict | None = None) -> dict:
        payload = {
            "access_key": self.access_key,
            "nonce":      str(uuid.uuid4()),
        }
        if query_params:
            from urllib.parse import urlencode
            query_str  = urlencode(query_params)
            hash_obj   = hashlib.sha512()
            hash_obj.update(query_str.encode())
            payload["query_hash"]     = hash_obj.hexdigest()
            payload["query_hash_alg"] = "SHA512"

        token = pyjwt.encode(payload, self.secret_key, algorithm="HS256")
        return {"Authorization": f"Bearer {token}"}

    def get_trade_history(self, days: int = 180) -> list:
        """완료된 주문을 최대 days일치 수집 (페이지 100건씩)"""
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
        print(f"  조회 기간: {cutoff:%Y-%m-%d} ~ {datetime.now():%Y-%m-%d}")

        all_orders, page = [], 1
        while True:
            params = {"state": "done", "limit": 100, "page": page, "order_by": "desc"}
            r = requests.get(
                f"{BASE_URL}/v1/orders",
                headers=self._headers(params),
                params=params,
                timeout=10,
            )
            r.raise_for_status()
            batch = r.json()
            if not batch:
                break

            # cutoff 이전 항목 제거
            filtered = []
            stop = False
            for o in batch:
                created = datetime.fromisoformat(o["created_at"])
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                if created < cutoff:
                    stop = True
                    break
                filtered.append(o)

            all_orders.extend(filtered)
            if stop or len(batch) < 100:
                break
            page += 1

        print(f"  ✓ {len(all_orders)}건 주문 수집")
        return [self._normalize(o) for o in all_orders]

    @staticmethod
    def _normalize(o: dict) -> dict:
        # 체결 평균가 계산
        exec_vol = float(o.get("executed_volume") or 0)
        price    = float(o.get("price") or 0)
        locked   = float(o.get("locked") or 0)
        ord_type = o.get("ord_type", "")

        if ord_type == "limit" and price:
            avg_price = price
        elif exec_vol > 0:
            # market buy: locked ≈ spent KRW, market sell: approximate
            avg_price = locked / exec_vol
        else:
            avg_price = price

        amount = avg_price * exec_vol

        # market: "KRW-BTC" → ticker = "BTC"
        market = o.get("market", "")
        parts  = market.split("-")
        currency = parts[0] if len(parts) >= 2 else "KRW"
        ticker   = parts[1] if len(parts) >= 2 else market

        dt_raw = o.get("created_at", "")
        try:
            dt = datetime.fromisoformat(dt_raw).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            dt = dt_raw

        side_raw = o.get("side", "")  # "bid"=매수, "ask"=매도
        return {
            "dt":       dt,
            "side":     "buy" if side_raw == "bid" else "sell",
            "ticker":   ticker,
            "name":     ticker,
            "qty":      exec_vol,
            "price":    avg_price,
            "amount":   amount,
            "currency": currency,
        }
