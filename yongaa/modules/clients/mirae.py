"""
미래에셋증권 Open API 클라이언트
- MiraeDomesticClient : 국내 주식 체결 내역
- MiraeAbroadClient   : 해외 주식 체결 내역

※ API 등록: https://openapi.miraeasset.com
  앱 등록 후 APP_KEY / APP_SECRET 발급

인증 방식: OAuth2 (appkey + appsecret → access_token)
반환 포맷: 표준 레코드 리스트
  {"dt", "side", "ticker", "name", "qty", "price", "amount", "currency"}

─────────────────────────────────────────────────────────────────
[API 엔드포인트 확인 방법]
미래에셋 개발자 포털에서 아래 TR을 검색하세요:
  국내: 주식 주문체결내역 조회
  해외: 해외주식 주문체결내역 조회
필드명이 실제 응답과 다를 경우 _normalize() 내 col_map을 수정하세요.
─────────────────────────────────────────────────────────────────
"""

import requests
from datetime import datetime, timedelta


class _MiraeBase:
    REAL_URL    = "https://openapi.miraeasset.com"
    SANDBOX_URL = "https://openapi-sandbox.miraeasset.com"

    def __init__(self, app_key: str, app_secret: str, account_no: str, is_mock: bool = False):
        self.app_key    = app_key
        self.app_secret = app_secret
        # 계좌번호 파싱 (예: "12345678-01" 또는 "1234567801")
        clean           = account_no.replace("-", "")
        self.account_no = account_no          # 원본 보관
        self.cano       = clean[:8]           # 앞 8자리
        self.acnt_cd    = clean[8:10]         # 뒤 2자리
        self.base_url   = self.SANDBOX_URL if is_mock else self.REAL_URL
        self.is_mock    = is_mock
        self.token      = None

    # ── 인증 ─────────────────────────────────────────────────────
    def authenticate(self):
        """OAuth2 access_token 발급"""
        r = requests.post(
            f"{self.base_url}/api/oauth/v1/token/get",
            json={
                "grant_type": "client_credentials",
                "appkey":     self.app_key,
                "appsecret":  self.app_secret,
            },
            timeout=10,
        )
        r.raise_for_status()
        body = r.json()

        # 미래에셋은 "access_token" 또는 "AccessToken" 키로 반환할 수 있음
        token = (
            body.get("access_token")
            or body.get("AccessToken")
            or body.get("token")
        )
        if not token:
            raise RuntimeError(f"미래에셋 인증 실패: {body}")
        self.token = token
        print("  ✓ 미래에셋 인증 완료")

    def _headers(self, tr_id: str) -> dict:
        return {
            "Content-Type":  "application/json; charset=utf-8",
            "authorization": f"Bearer {self.token}",
            "appkey":        self.app_key,
            "appsecret":     self.app_secret,
            "tr_id":         tr_id,
        }

    def _paginate(self, url: str, tr_id: str, base_params: dict) -> list:
        """페이지네이션 공통 처리"""
        all_rows, fk, nk = [], "", ""
        while True:
            params = {**base_params, "CTX_AREA_FK": fk, "CTX_AREA_NK": nk}
            r = requests.get(url, headers=self._headers(tr_id), params=params, timeout=10)
            r.raise_for_status()
            body = r.json()

            rt_cd = body.get("rt_cd") or body.get("rtCd") or body.get("result_code")
            if rt_cd not in (None, "0", 0, "00"):
                raise RuntimeError(f"미래에셋 API 오류: {body.get('msg1') or body}")

            # output 키 탐색 (응답 구조가 다를 수 있음)
            rows = (
                body.get("output1")
                or body.get("Output1")
                or body.get("data")
                or body.get("list")
                or []
            )
            all_rows.extend(rows)

            fk = body.get("ctx_area_fk", body.get("CTX_AREA_FK", "")).strip()
            nk = body.get("ctx_area_nk", body.get("CTX_AREA_NK", "")).strip()
            if not fk:
                break
        return all_rows


class MiraeDomesticClient(_MiraeBase):
    """
    미래에셋 국내주식 체결 내역 조회
    TR ID: TTTC8001R (실전) / VTTC8001R (모의)  ← KIS와 동일할 수 있음
    ※ 미래에셋 개발자 포털에서 정확한 TR_ID 확인 필요
    """

    def get_trade_history(self, days: int = 180) -> list:
        end_dt   = datetime.now()
        start_dt = end_dt - timedelta(days=days)
        tr_id    = "VTTC8001R" if self.is_mock else "TTTC8001R"
        url      = f"{self.base_url}/api/v1/trading/domestic/inquire-daily-ccld"

        print(f"  조회 기간: {start_dt:%Y-%m-%d} ~ {end_dt:%Y-%m-%d}")

        base_params = {
            "CANO":            self.cano,
            "ACNT_PRDT_CD":    self.acnt_cd,
            "INQR_STRT_DT":    start_dt.strftime("%Y%m%d"),
            "INQR_END_DT":     end_dt.strftime("%Y%m%d"),
            "SLL_BUY_DVSN_CD": "00",   # 00=전체
            "INQR_DVSN":       "01",    # 01=정순
            "PDNO":            "",
            "CCLD_DVSN":       "01",    # 01=체결만
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
        """
        미래에셋 국내 체결 레코드 → 표준 포맷
        필드명은 KIS와 유사하나 다를 수 있음 → col_map에서 조정
        """
        col_map = {
            "date":       ("ord_dt",   "ordr_dt",   "order_dt"),
            "time":       ("ord_tmd",  "ordr_tmd",  "order_tmd"),
            "side_code":  ("sll_buy_dvsn_cd", "slbyCd", "buy_sell_gb"),
            "ticker":     ("pdno",     "stk_cd",    "isin_code"),
            "name":       ("prdt_name","stk_nm",    "item_name"),
            "qty":        ("tot_ccld_qty", "ccld_qty", "exec_qty"),
            "price":      ("avg_prvs",     "ccld_prc", "exec_prc"),
            "amount":     ("tot_ccld_amt", "ccld_amt", "exec_amt"),
        }

        def pick(*keys):
            for k in keys:
                v = r.get(k)
                if v is not None and str(v).strip():
                    return str(v)
            return ""

        def pick_num(*keys):
            for k in keys:
                v = str(r.get(k, "0")).replace(",", "").strip()
                try:
                    return float(v)
                except ValueError:
                    pass
            return 0.0

        date_s = pick(*col_map["date"])
        time_s = pick(*col_map["time"])
        try:
            dt = datetime.strptime(date_s + time_s, "%Y%m%d%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            dt = f"{date_s} {time_s}".strip() or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        side_code = pick(*col_map["side_code"])
        # 02=매수, 01=매도 (KIS 기준, 미래에셋 다를 수 있음)
        side = "buy" if side_code in ("02", "2", "B", "BUY", "매수") else "sell"

        qty    = pick_num(*col_map["qty"])
        price  = pick_num(*col_map["price"])
        amount = pick_num(*col_map["amount"]) or qty * price

        return {
            "dt":       dt,
            "side":     side,
            "ticker":   pick(*col_map["ticker"]),
            "name":     pick(*col_map["name"]),
            "qty":      qty,
            "price":    price,
            "amount":   amount,
            "currency": "KRW",
        }


class MiraeAbroadClient(_MiraeBase):
    """
    미래에셋 해외주식 체결 내역 조회
    TR ID: TTTS3035R (실전) / VTTS3035R (모의)
    ※ 미래에셋 개발자 포털에서 정확한 TR_ID 및 엔드포인트 확인 필요
    """

    def get_trade_history(self, days: int = 180) -> list:
        end_dt   = datetime.now()
        start_dt = end_dt - timedelta(days=days)
        tr_id    = "VTTS3035R" if self.is_mock else "TTTS3035R"
        url      = f"{self.base_url}/api/v1/trading/overseas/inquire-ccnl"

        print(f"  조회 기간: {start_dt:%Y-%m-%d} ~ {end_dt:%Y-%m-%d}")

        base_params = {
            "CANO":            self.cano,
            "ACNT_PRDT_CD":    self.acnt_cd,
            "PDNO":            "",
            "ORD_STRT_DT":     start_dt.strftime("%Y%m%d"),
            "ORD_END_DT":      end_dt.strftime("%Y%m%d"),
            "SLL_BUY_DVSN_CD": "00",
            "CCLD_NCCS_DVS":   "01",
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
        col_map = {
            "date":      ("ord_dt",   "ordr_dt"),
            "time":      ("ord_tmd",  "ordr_tmd"),
            "side_code": ("sll_buy_dvsn_cd", "slbyCd"),
            "ticker":    ("ovrs_pdno", "pdno", "stk_cd"),
            "name":      ("prdt_name", "stk_nm"),
            "qty":       ("ft_ccld_qty",   "ccld_qty",  "exec_qty"),
            "price":     ("ft_ccld_unpr3", "ccld_prc",  "exec_prc"),
            "amount":    ("ft_ccld_amt3",  "ccld_amt",  "exec_amt"),
            "currency":  ("tr_crcy_cd",    "crcy_cd",   "crcyCd"),
        }

        def pick(*keys):
            for k in keys:
                v = r.get(k)
                if v is not None and str(v).strip():
                    return str(v)
            return ""

        def pick_num(*keys):
            for k in keys:
                v = str(r.get(k, "0")).replace(",", "").strip()
                try:
                    return float(v)
                except ValueError:
                    pass
            return 0.0

        date_s = pick(*col_map["date"])
        time_s = pick(*col_map["time"])
        try:
            dt = datetime.strptime(date_s + time_s, "%Y%m%d%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            dt = f"{date_s} {time_s}".strip() or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        side_code = pick(*col_map["side_code"])
        side      = "buy" if side_code in ("02", "2", "B", "BUY", "매수") else "sell"

        qty      = pick_num(*col_map["qty"])
        price    = pick_num(*col_map["price"])
        amount   = pick_num(*col_map["amount"]) or qty * price
        currency = pick(*col_map["currency"]) or "USD"

        return {
            "dt":       dt,
            "side":     side,
            "ticker":   pick(*col_map["ticker"]),
            "name":     pick(*col_map["name"]),
            "qty":      qty,
            "price":    price,
            "amount":   amount,
            "currency": currency,
        }
