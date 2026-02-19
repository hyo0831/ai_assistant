"""
한국투자증권(KIS) Open API 클라이언트
- KISDomesticClient : 국내 주식 체결 내역
- KISAbroadClient   : 해외 주식 체결 내역
반환 포맷 (표준화된 레코드 리스트):
  [{"dt": "2024-01-15 09:30:00", "side": "buy"|"sell",
    "ticker": str, "name": str,
    "qty": float, "price": float, "amount": float,
    "currency": "KRW"|"USD"|...}, ...]
"""

import requests
from datetime import datetime, timedelta


class _KISBase:
    REAL_URL = "https://openapi.kis.co.kr"
    MOCK_URL = "https://openapivts.koreainvestment.com:29443"

    def __init__(self, app_key: str, app_secret: str, account_no: str, is_mock: bool = False):
        self.app_key    = app_key
        self.app_secret = app_secret
        clean           = account_no.replace("-", "")
        self.cano       = clean[:8]
        self.acnt_cd    = clean[8:10]
        self.base_url   = self.MOCK_URL if is_mock else self.REAL_URL
        self.is_mock    = is_mock
        self.token      = None

    def authenticate(self):
        r = requests.post(
            f"{self.base_url}/oauth2/tokenP",
            json={"grant_type": "client_credentials",
                  "appkey": self.app_key, "appsecret": self.app_secret},
            timeout=10,
        )
        r.raise_for_status()
        body = r.json()
        if "access_token" not in body:
            raise RuntimeError(f"KIS 인증 실패: {body}")
        self.token = body["access_token"]
        print("  ✓ KIS 인증 완료")

    def _headers(self, tr_id: str) -> dict:
        return {
            "Content-Type":  "application/json; charset=utf-8",
            "authorization": f"Bearer {self.token}",
            "appkey":        self.app_key,
            "appsecret":     self.app_secret,
            "tr_id":         tr_id,
        }

    def _paginate(self, url, tr_id, base_params) -> list:
        """KIS 페이지네이션 공통 처리 (CTX_AREA_FK100/NK100 방식)"""
        all_rows, fk, nk = [], "", ""
        while True:
            params = {**base_params, "CTX_AREA_FK100": fk, "CTX_AREA_NK100": nk}
            r = requests.get(url, headers=self._headers(tr_id), params=params, timeout=10)
            r.raise_for_status()
            body = r.json()
            if body.get("rt_cd") != "0":
                raise RuntimeError(f"KIS API 오류: {body.get('msg1')}")
            all_rows.extend(body.get("output1", []))
            fk = body.get("ctx_area_fk100", "").strip()
            nk = body.get("ctx_area_nk100", "").strip()
            if not fk:
                break
        return all_rows


class KISDomesticClient(_KISBase):
    """국내 주식 체결 내역 (TTTC8001R)"""

    def get_trade_history(self, days: int = 180) -> list:
        end_dt   = datetime.now()
        start_dt = end_dt - timedelta(days=days)
        tr_id    = "VTTC8001R" if self.is_mock else "TTTC8001R"
        url      = f"{self.base_url}/uapi/domestic-stock/v1/trading/inquire-daily-ccld"
        print(f"  조회 기간: {start_dt:%Y-%m-%d} ~ {end_dt:%Y-%m-%d}")

        base_params = {
            "CANO":            self.cano,
            "ACNT_PRDT_CD":    self.acnt_cd,
            "INQR_STRT_DT":    start_dt.strftime("%Y%m%d"),
            "INQR_END_DT":     end_dt.strftime("%Y%m%d"),
            "SLL_BUY_DVSN_CD": "00",   # 전체
            "INQR_DVSN":       "01",    # 정순
            "PDNO":            "",
            "CCLD_DVSN":       "01",    # 체결만
            "ORD_GNO_BRNO":    "",
            "ODNO":            "",
            "INQR_DVSN_3":     "00",
            "INQR_DVSN_1":     "",
        }
        raw = self._paginate(url, tr_id, base_params)
        print(f"  ✓ {len(raw)}건 체결 내역 수집")
        return [self._normalize(r) for r in raw]

    @staticmethod
    def _normalize(r: dict) -> dict:
        def n(k): return float(str(r.get(k, "0")).replace(",", "") or "0")
        dt_str = r.get("ord_dt", "") + r.get("ord_tmd", "")
        try:
            dt = datetime.strptime(dt_str, "%Y%m%d%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            dt = dt_str
        side_code = str(r.get("sll_buy_dvsn_cd", ""))
        return {
            "dt":       dt,
            "side":     "buy" if side_code == "02" else "sell",
            "ticker":   r.get("pdno", ""),
            "name":     r.get("prdt_name", ""),
            "qty":      n("tot_ccld_qty"),
            "price":    n("avg_prvs"),
            "amount":   n("tot_ccld_amt"),
            "currency": "KRW",
        }


class KISAbroadClient(_KISBase):
    """
    해외 주식 체결 내역 (TTTS3035R)
    ※ 해외주식 output1 주요 필드:
       ord_dt, ord_tmd, sll_buy_dvsn_cd
       ovrs_pdno(종목코드), prdt_name
       ft_ccld_qty(체결수량), ft_ccld_unpr3(체결단가), ft_ccld_amt3(체결금액)
       tr_crcy_cd(통화코드)
    """

    def get_trade_history(self, days: int = 180) -> list:
        end_dt   = datetime.now()
        start_dt = end_dt - timedelta(days=days)
        tr_id    = "VTTS3035R" if self.is_mock else "TTTS3035R"
        url      = f"{self.base_url}/uapi/overseas-stock/v1/trading/inquire-ccnl"
        print(f"  조회 기간: {start_dt:%Y-%m-%d} ~ {end_dt:%Y-%m-%d}")

        base_params = {
            "CANO":            self.cano,
            "ACNT_PRDT_CD":    self.acnt_cd,
            "PDNO":            "",
            "ORD_STRT_DT":     start_dt.strftime("%Y%m%d"),
            "ORD_END_DT":      end_dt.strftime("%Y%m%d"),
            "SLL_BUY_DVSN_CD": "00",
            "CCLD_NCCS_DVS":   "01",   # 체결만
            "OVRS_EXCG_CD":    "",
            "SORT_SQN":        "DS",
            "ORD_GNO_BRNO":    "",
            "ODNO":            "",
        }
        raw = self._paginate(url, tr_id, base_params)
        print(f"  ✓ {len(raw)}건 체결 내역 수집")
        return [self._normalize(r) for r in raw]

    @staticmethod
    def _normalize(r: dict) -> dict:
        def n(*keys):
            for k in keys:
                v = str(r.get(k, "0")).replace(",", "")
                if v:
                    try:
                        return float(v)
                    except ValueError:
                        pass
            return 0.0
        dt_str = r.get("ord_dt", "") + r.get("ord_tmd", "")
        try:
            dt = datetime.strptime(dt_str, "%Y%m%d%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            dt = dt_str
        side_code = str(r.get("sll_buy_dvsn_cd", ""))
        return {
            "dt":       dt,
            "side":     "buy" if side_code == "02" else "sell",
            "ticker":   r.get("ovrs_pdno", r.get("pdno", "")),
            "name":     r.get("prdt_name", ""),
            "qty":      n("ft_ccld_qty", "tot_ccld_qty"),
            "price":    n("ft_ccld_unpr3", "avg_prvs"),
            "amount":   n("ft_ccld_amt3", "tot_ccld_amt"),
            "currency": r.get("tr_crcy_cd", "USD"),
        }
