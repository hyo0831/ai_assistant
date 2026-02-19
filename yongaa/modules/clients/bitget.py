"""
비트겟(Bitget) 클라이언트 (ccxt 기반)
pip install ccxt

선물(swap) 계정 우선, 현물(spot) 폴백.
ccxt 표준 포맷 → 표준 레코드 리스트로 변환.
반환: {"dt", "side", "ticker", "name", "qty", "price", "amount", "currency"}
"""

from datetime import datetime, timedelta


class BitgetClient:
    def __init__(self, api_key: str, api_secret: str, passphrase: str):
        self.api_key    = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase  # 비트겟은 passphrase 필수
        self._exchange  = None

    def authenticate(self):
        try:
            import ccxt
        except ImportError:
            raise ImportError("ccxt 설치 필요: pip install ccxt")

        self._exchange = ccxt.bitget({
            "apiKey":          self.api_key,
            "secret":          self.api_secret,
            "password":        self.passphrase,   # Bitget passphrase
            "enableRateLimit": True,
            "options": {
                "defaultType": "swap",  # 선물 계정 우선
            },
        })

        try:
            self._exchange.fetch_balance()
            print("  ✓ 비트겟 인증 완료 (선물/swap)")
        except Exception as e:
            raise RuntimeError(f"비트겟 인증 실패: {e}")

    def get_trade_history(self, days: int = 180) -> list:
        """
        fetch_my_trades: ccxt bitget은 symbol 지정 없이도 동작.
        안 되면 balance에서 심볼 목록 추출 후 개별 조회.
        """
        since_ms = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)

        all_records = []

        # ── 1차 시도: symbol=None 전체 조회 ──────────────────────
        try:
            trades = self._exchange.fetch_my_trades(
                symbol=None,
                since=since_ms,
                limit=500,
            )
            if trades:
                all_records = [self._normalize(t) for t in trades if t]
                print(f"  ✓ {len(all_records)}건 수집 (비트겟 전체)")
                return [r for r in all_records if r]
        except Exception:
            pass  # symbol 지정 필요 → 2차 시도

        # ── 2차 시도: 잔고에서 심볼 추출 후 개별 조회 ────────────
        try:
            balance = self._exchange.fetch_balance()
            symbols = [
                f"{asset}/USDT:{asset}" if "swap" in str(self._exchange.options.get("defaultType","")) else f"{asset}/USDT"
                for asset, info in balance.get("total", {}).items()
                if float(info or 0) > 0 and asset not in ("USDT", "BUSD", "USD")
            ]

            for sym in symbols[:20]:  # 최대 20개 심볼
                try:
                    trades = self._exchange.fetch_my_trades(
                        symbol=sym,
                        since=since_ms,
                        limit=500,
                    )
                    recs = [self._normalize(t) for t in (trades or []) if t]
                    recs = [r for r in recs if r]
                    if recs:
                        print(f"  [{sym}] {len(recs)}건")
                        all_records.extend(recs)
                except Exception:
                    pass

        except Exception as e:
            raise RuntimeError(f"비트겟 데이터 조회 실패: {e}")

        print(f"  ✓ 총 {len(all_records)}건 수집 (비트겟)")
        return all_records

    @staticmethod
    def _normalize(t: dict) -> dict | None:
        """ccxt 표준 trade 포맷 → 표준 레코드"""
        if not t:
            return None

        ts    = t.get("timestamp", 0)
        dt    = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M:%S") if ts else ""
        side  = str(t.get("side", "")).lower()
        price = float(t.get("price", 0) or 0)
        qty   = float(t.get("amount", 0) or 0)
        cost  = float(t.get("cost", 0) or qty * price)

        if qty <= 0 or price <= 0:
            return None

        # symbol: "BTC/USDT:USDT" or "BTC/USDT" → ticker = "BTC", currency = "USDT"
        symbol   = str(t.get("symbol", ""))
        parts    = symbol.split("/")
        ticker   = parts[0] if parts else symbol
        currency = parts[1].split(":")[0] if len(parts) > 1 else "USDT"

        return {
            "dt":       dt,
            "side":     "buy" if side == "buy" else "sell",
            "ticker":   ticker,
            "name":     ticker,
            "qty":      qty,
            "price":    price,
            "amount":   cost,
            "currency": currency,
        }
