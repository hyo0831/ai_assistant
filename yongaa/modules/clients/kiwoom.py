"""
키움증권 클라이언트 (pykiwoom 기반)
※ 실행 환경 요구사항:
   - Windows OS
   - 키움증권 HTS(영웅문) 설치 완료
   - 32bit Python 또는 pykiwoom 설치
   - pip install pykiwoom

국내(KR): TR opt10075 - 체결기준잔고 (당일 매매 내역)
해외(US): TR opw30001 - 해외주식잔고

반환: 표준 레코드 리스트
  {"dt", "side", "ticker", "name", "qty", "price", "amount", "currency"}
"""

from datetime import datetime


class KiwoomDomesticClient:
    """키움 국내주식"""

    def __init__(self):
        # pykiwoom은 API Key 불필요 → GUI 로그인 방식
        self._kiwoom = None
        self.account = None

    def authenticate(self):
        try:
            from pykiwoom.kiwoom import Kiwoom
        except ImportError:
            raise ImportError(
                "pykiwoom 설치 필요: pip install pykiwoom\n"
                "  ※ 키움 HTS(영웅문) 설치 및 실행 후 재시도하세요."
            )

        self._kiwoom = Kiwoom()
        self._kiwoom.CommConnect(block=True)  # GUI 로그인 팝업 발생

        accounts = self._kiwoom.GetLoginInfo("ACCNO")
        if not accounts:
            raise RuntimeError("계좌 정보를 가져올 수 없습니다.")

        if len(accounts) == 1:
            self.account = accounts[0].strip()
        else:
            print("\n  복수 계좌 감지:")
            for i, acc in enumerate(accounts, 1):
                print(f"    {i}. {acc.strip()}")
            sel = int(input("  사용할 계좌 선택 → ").strip()) - 1
            self.account = accounts[sel].strip()

        print(f"  ✓ 키움 로그인 완료: {self.account}")

    def get_trade_history(self, days: int = 180) -> list:
        # opt10075: 체결기준잔고 (당일 기준, 날짜 파라미터 없음)
        # 주의: 이 TR은 당일 데이터만 반환 → 180일치 누적 불가
        # 향후 개선: opt10081(체결장부가) 또는 다중 날짜 루프 적용 예정
        raw = self._kiwoom.block_request(
            "opt10075",
            계좌번호=self.account,
            매매구분=0,   # 0=전체, 1=매도, 2=매수
            체결구분=0,   # 0=전체, 1=체결
            output="체결기준잔고",
            next=0,
        )

        if raw is None:
            print("  [경고] 체결 데이터 없음 (opt10075)")
            return []

        items = self._extract_items(raw)
        records = []
        for item in items:
            records.extend(self._normalize(item, "KRW"))

        print(f"  ✓ {len(records)}건 수집 (키움 국내 당일 체결 기준)")
        return records

    @staticmethod
    def _extract_items(raw) -> list:
        if isinstance(raw, dict):
            for key in ("output1", "체결기준잔고", "output"):
                if key in raw and raw[key]:
                    return raw[key]
        try:
            import pandas as pd
            if isinstance(raw, pd.DataFrame):
                return raw.to_dict("records")
        except ImportError:
            pass
        if isinstance(raw, list):
            return raw
        return []

    @staticmethod
    def _normalize(item: dict, currency: str) -> list:
        def g(*keys):
            for k in keys:
                v = str(item.get(k, "0") if isinstance(item, dict) else "0")
                v = v.replace(",", "").replace("+", "").strip()
                try:
                    return float(v)
                except ValueError:
                    pass
            return 0.0

        ticker   = str(item.get("종목코드", "") if isinstance(item, dict) else "").strip()
        name     = str(item.get("종목명",   "") if isinstance(item, dict) else "")
        buy_qty  = g("매입수량", "매수수량")
        sell_qty = g("매도수량")
        buy_px   = g("매입단가", "매수단가", "매입평균가")
        sell_px  = g("매도단가", "매도평균가")
        now_str  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        result = []
        if buy_qty > 0 and buy_px > 0:
            result.append({
                "dt": now_str, "side": "buy",
                "ticker": ticker, "name": name,
                "qty": buy_qty, "price": buy_px,
                "amount": buy_qty * buy_px, "currency": currency,
            })
        if sell_qty > 0 and sell_px > 0:
            result.append({
                "dt": now_str, "side": "sell",
                "ticker": ticker, "name": name,
                "qty": sell_qty, "price": sell_px,
                "amount": sell_qty * sell_px, "currency": currency,
            })
        return result


class KiwoomAbroadClient(KiwoomDomesticClient):
    """키움 해외주식 (opw30001)"""

    def get_trade_history(self, days: int = 180) -> list:
        raw = self._kiwoom.block_request(
            "opw30001",
            계좌번호=self.account,
            비밀번호="",
            조회구분=2,
            output="해외주식잔고",
            next=0,
        )

        if raw is None:
            print("  [경고] 해외 체결 데이터 없음 (opw30001)")
            return []

        items   = self._extract_items(raw)
        records = []
        for item in items:
            records.extend(self._normalize(item, "USD"))

        print(f"  ✓ {len(records)}건 수집 (키움 해외 잔고 기준)")
        return records
