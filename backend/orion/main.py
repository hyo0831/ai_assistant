#!/usr/bin/env python3
"""
ORION 투자 진단 시스템 v0.1  ─  터미널 데모
한국투자증권 Open API + OpenAI GPT-4o
"""

import sys
import requests
import pandas as pd
from datetime import datetime, timedelta
from openai import OpenAI


# ══════════════════════════════════════════════════════════════════
#  유틸
# ══════════════════════════════════════════════════════════════════

def bar(title=""):
    print("\n" + "=" * 62)
    if title:
        print(f"  {title}")
        print("=" * 62)


# ══════════════════════════════════════════════════════════════════
#  1. KIS API 클라이언트
# ══════════════════════════════════════════════════════════════════

class KISClient:
    REAL_URL = "https://openapi.kis.co.kr"
    MOCK_URL = "https://openapivts.koreainvestment.com:29443"

    def __init__(self, app_key: str, app_secret: str, account_no: str, is_mock: bool = False):
        self.app_key    = app_key
        self.app_secret = app_secret
        clean           = account_no.replace("-", "")
        self.cano       = clean[:8]          # 계좌번호 앞 8자리
        self.acnt_cd    = clean[8:10]        # 계좌번호 뒤 2자리
        self.base_url   = self.MOCK_URL if is_mock else self.REAL_URL
        self.is_mock    = is_mock
        self.token      = None

    # ── 인증 ──────────────────────────────────────────────────────
    def authenticate(self):
        r = requests.post(
            f"{self.base_url}/oauth2/tokenP",
            json={
                "grant_type": "client_credentials",
                "appkey":     self.app_key,
                "appsecret":  self.app_secret,
            },
            timeout=10,
        )
        r.raise_for_status()
        body = r.json()
        if "access_token" not in body:
            raise RuntimeError(f"인증 실패: {body}")
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

    # ── 일별 주문 체결 조회 (페이지 자동 순회) ────────────────────
    def get_trade_history(self, days: int = 180) -> list:
        end_dt   = datetime.now()
        start_dt = end_dt - timedelta(days=days)
        tr_id    = "VTTC8001R" if self.is_mock else "TTTC8001R"
        url      = f"{self.base_url}/uapi/domestic-stock/v1/trading/inquire-daily-ccld"

        print(f"  조회 기간: {start_dt.strftime('%Y-%m-%d')} ~ {end_dt.strftime('%Y-%m-%d')}")

        all_rows, fk, nk = [], "", ""
        while True:
            params = {
                "CANO":           self.cano,
                "ACNT_PRDT_CD":   self.acnt_cd,
                "INQR_STRT_DT":   start_dt.strftime("%Y%m%d"),
                "INQR_END_DT":    end_dt.strftime("%Y%m%d"),
                "SLL_BUY_DVSN_CD": "00",   # 00=전체
                "INQR_DVSN":      "01",     # 01=정순
                "PDNO":           "",
                "CCLD_DVSN":      "01",     # 01=체결만
                "ORD_GNO_BRNO":   "",
                "ODNO":           "",
                "INQR_DVSN_3":    "00",
                "INQR_DVSN_1":    "",
                "CTX_AREA_FK100": fk,
                "CTX_AREA_NK100": nk,
            }
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

        print(f"  ✓ 총 {len(all_rows)}건 체결 내역 수집")
        return all_rows


# ══════════════════════════════════════════════════════════════════
#  2. 데이터 전처리 & 지표 산출
# ══════════════════════════════════════════════════════════════════

def _to_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str).str.replace(",", "", regex=False),
        errors="coerce",
    ).fillna(0)


def process_trades(raw: list) -> dict:
    """
    KIS output1 레코드 리스트를 받아 매매 지표를 산출한다.

    핵심 필드 (KIS TTTC8001R output1):
      ord_dt          주문일자 (YYYYMMDD)
      ord_tmd         주문시각 (HHMMSS)
      sll_buy_dvsn_cd 01=매도, 02=매수
      pdno            종목코드
      prdt_name       종목명
      tot_ccld_qty    총체결수량
      avg_prvs        체결평균가
      tot_ccld_amt    총체결금액
    """
    if not raw:
        return {"error": "체결 내역 없음", "total_trades": 0}

    df = pd.DataFrame(raw)

    # 필드 존재 확인 (API 응답이 달라질 경우 여기서 조정)
    needed = {"ord_dt", "ord_tmd", "sll_buy_dvsn_cd", "pdno", "tot_ccld_qty", "avg_prvs"}
    missing = needed - set(df.columns)
    if missing:
        return {"error": f"필드 누락: {missing}", "total_trades": 0, "raw_columns": list(df.columns)}

    df = df.rename(columns={
        "ord_dt":           "date",
        "ord_tmd":          "time",
        "sll_buy_dvsn_cd":  "side",
        "pdno":             "ticker",
        "prdt_name":        "name",
        "tot_ccld_qty":     "qty",
        "avg_prvs":         "avg_price",
        "tot_ccld_amt":     "amount",
    })

    df["qty"]       = _to_num(df["qty"])
    df["avg_price"] = _to_num(df["avg_price"])
    df["amount"]    = _to_num(df.get("amount", pd.Series(["0"] * len(df))))
    df["datetime"]  = pd.to_datetime(
        df["date"] + df["time"], format="%Y%m%d%H%M%S", errors="coerce"
    )

    # ── FIFO 매매 페어링 ──────────────────────────────────────────
    completed, martingale_count = [], 0

    for ticker, grp in df.groupby("ticker"):
        grp = grp.sort_values("datetime").reset_index(drop=True)
        buy_queue = []          # {qty, price, dt}
        consec_buy = 0

        for _, row in grp.iterrows():
            side  = str(row["side"])
            qty   = row["qty"]
            price = row["avg_price"]
            dt    = row["datetime"]

            if side == "02":    # 매수
                buy_queue.append({"qty": qty, "price": price, "dt": dt})
                consec_buy += 1
                if consec_buy > 1:
                    martingale_count += 1   # 연속 매수 = 물타기 의심

            elif side == "01":  # 매도 → FIFO 매칭
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
            "error": "완료된 매매 없음 (미청산 포지션만 존재하거나 데이터 부족)",
            "total_trades": 0,
            "raw_count": len(df),
        }

    tdf  = pd.DataFrame(completed)
    tot  = len(tdf)
    wins = int(tdf["win"].sum())
    loss = tot - wins

    avg_profit = tdf.loc[tdf["win"],  "pnl_pct"].mean() if wins else 0.0
    avg_loss   = abs(tdf.loc[~tdf["win"], "pnl_pct"].mean()) if loss else 0.0
    rr_ratio   = round(avg_profit / avg_loss, 2) if avg_loss else 99.99

    tdf["cum_pnl"]  = tdf["pnl"].cumsum()
    tdf["peak"]     = tdf["cum_pnl"].cummax()
    tdf["drawdown"] = tdf["cum_pnl"] - tdf["peak"]
    mdd             = tdf["drawdown"].min()

    avg_hold = tdf["holding_hours"].dropna().mean()

    return {
        "total_trades":     tot,
        "win_trades":       wins,
        "loss_trades":      loss,
        "win_rate":         round(wins / tot * 100, 1),
        "avg_profit_pct":   round(avg_profit, 2),
        "avg_loss_pct":     round(avg_loss, 2),
        "rr_ratio":         rr_ratio,
        "total_pnl":        round(tdf["pnl"].sum(), 0),
        "mdd":              round(mdd, 0),
        "avg_holding_hours": round(avg_hold, 1) if pd.notnull(avg_hold) else None,
        "martingale_count": martingale_count,
    }


# ══════════════════════════════════════════════════════════════════
#  3. 설문지
# ══════════════════════════════════════════════════════════════════

SURVEY_QUESTIONS = [
    ("q1",  "1. 주로 매매하는 종목 성격\n"
            "   ① 소형주/알트코인   ② 우량주   ③ 박스권 종목   또는 직접 입력\n"
            "   → "),
    ("q2",  "2. 진입 시 가장 중요한 도구(지표)\n"
            "   ① 차트패턴/캔들    ② 실적/뉴스    ③ 수급(외인·기관)   또는 직접 입력\n"
            "   → "),
    ("q3",  "3. 선호하는 진입 타이밍\n"
            "   ① 돌파매매    ② 눌림목    ③ 역추세(과매도 반등)   또는 직접 입력\n"
            "   → "),
    ("q4",  "4. 평균 포지션 보유 기간\n"
            "   ① 스캘핑(분 단위)    ② 데이트레이딩    ③ 스윙(며칠~몇 주)   또는 직접 입력\n"
            "   → "),
    ("q5",  "5. 목표 손익비 (TP : SL)\n"
            "   ① 1:1    ② 2:1    ③ 3:1 이상   또는 직접 입력\n"
            "   → "),
    ("q6",  "6. 손실 발생 시 대응 방식\n"
            "   ① 기계적 손절    ② 물타기 후 반등 탈출    ③ 존버   또는 직접 입력\n"
            "   → "),
    ("q7",  "7. 일일 최대 손실(Daily Stop) 원칙 있습니까?\n"
            "   ① 있다    ② 없다   또는 직접 입력\n"
            "   → "),
    ("q8",  "8. 매매 결정 시 가장 큰 영향 요인\n"
            "   ① 나만의 원칙    ② 커뮤니티/전문가 의견    ③ 직감   또는 직접 입력\n"
            "   → "),
    ("q9",  "9. 수익 발생 후 다음 매매 태도\n"
            "   ① 더 보수적으로    ② 더 공격적으로   또는 직접 입력\n"
            "   → "),
    ("q10", "10. AI가 반드시 알아야 할 나만의 필살기가 있다면?\n"
            "    → "),
]


def run_survey() -> dict:
    bar("Step 3. 사냥꾼 본능 진단 설문")
    print("  (숫자 또는 직접 입력 모두 가능합니다)\n")
    answers = {}
    for key, question in SURVEY_QUESTIONS:
        ans = input(f"  {question}").strip()
        answers[key] = ans
        print()
    return answers


# ══════════════════════════════════════════════════════════════════
#  4. 점수·티어 산출
# ══════════════════════════════════════════════════════════════════

TIERS = [
    (90, "챌린저"),
    (80, "그랜드마스터"),
    (70, "마스터"),
    (60, "다이아몬드"),
    (50, "플래티넘"),
    (40, "골드"),
    (30, "실버"),
    (0,  "브론즈"),
]


def calc_score(m: dict) -> int:
    score  = 0
    score += min(40, m.get("win_rate", 0) * 0.4)          # 승률 최대 40점
    score += min(40, m.get("rr_ratio", 0) * 13.3)         # 손익비 최대 40점
    score -= min(20, m.get("martingale_count", 0) * 2)    # 물타기 페널티
    return max(0, min(100, int(score)))


def get_tier(score: int) -> str:
    for threshold, tier in TIERS:
        if score >= threshold:
            return tier
    return "브론즈"


# ══════════════════════════════════════════════════════════════════
#  5. AI 융합 분석
# ══════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """당신은 ORION 투자 진단 AI입니다.
사용자의 실제 매매 데이터와 설문 응답을 교차 분석하여 다음 항목을 순서대로 출력하세요.
마크다운 없이 깔끔한 텍스트로만 작성합니다.

[1] 매매 스타일 요약 (3줄 이내)
[2] 강점 2가지 / 약점 2가지
[3] 설문 vs 실제 데이터 일치 여부 (원칙 준수율 판단)
[4] 최적 TP/SL 수치 추천 (과거 데이터 기반 근거 포함)
[5] AI 한마디 (핵심 조언 1문장)"""


def ai_analyze(metrics: dict, survey: dict, openai_key: str):
    score = calc_score(metrics)
    tier  = get_tier(score)

    user_msg = f"""
[실제 매매 데이터 - 최근 180일]
- 총 완결 거래 : {metrics.get('total_trades', 'N/A')}건
- 승률          : {metrics.get('win_rate', 'N/A')}%
- 평균 익절     : +{metrics.get('avg_profit_pct', 'N/A')}%
- 평균 손절     : -{metrics.get('avg_loss_pct', 'N/A')}%
- 실질 손익비   : {metrics.get('rr_ratio', 'N/A')} : 1
- 총 손익       : {metrics.get('total_pnl', 'N/A'):,}원
- MDD           : {metrics.get('mdd', 'N/A'):,}원
- 평균 보유시간 : {metrics.get('avg_holding_hours', 'N/A')}시간
- 물타기 횟수   : {metrics.get('martingale_count', 'N/A')}회
- 종합 점수     : {score}점  →  {tier} 등급

[설문 응답]
- 선호 종목    : {survey.get('q1', '')}
- 진입 도구    : {survey.get('q2', '')}
- 진입 타이밍  : {survey.get('q3', '')}
- 보유 기간    : {survey.get('q4', '')}
- 목표 손익비  : {survey.get('q5', '')}
- 손실 대응    : {survey.get('q6', '')}
- Daily Stop   : {survey.get('q7', '')}
- 결정 요인    : {survey.get('q8', '')}
- 수익 후 태도 : {survey.get('q9', '')}
- 필살기       : {survey.get('q10', '')}
"""

    client   = OpenAI(api_key=openai_key)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_msg},
        ],
        temperature=0.7,
    )
    return response.choices[0].message.content, score, tier


# ══════════════════════════════════════════════════════════════════
#  Main
# ══════════════════════════════════════════════════════════════════

def main():
    bar("ORION 투자 진단 시스템 v0.1")
    print("  한국투자증권 Open API  +  OpenAI GPT-4o")

    # ── Step 1: API 키 입력 ───────────────────────────────────────
    bar("Step 1. API 키 입력")
    app_key    = input("  KIS App Key      : ").strip()
    app_secret = input("  KIS App Secret   : ").strip()
    account_no = input("  계좌번호 (예: 50123456-01) : ").strip()
    openai_key = input("  OpenAI API Key   : ").strip()
    is_mock    = input("  모의투자 계좌입니까? (y/n) : ").strip().lower() == "y"

    # ── Step 2: 데이터 수집 ───────────────────────────────────────
    bar("Step 2. 180일 매매 데이터 수집")
    kis = KISClient(app_key, app_secret, account_no, is_mock)

    try:
        kis.authenticate()
        raw = kis.get_trade_history(days=180)
    except Exception as e:
        print(f"\n  [오류] KIS API 호출 실패: {e}")
        sys.exit(1)

    if not raw:
        print("  체결 내역이 없습니다. 종료합니다.")
        sys.exit(0)

    # ── Step 3(데이터): 전처리 & 지표 산출 ───────────────────────
    bar("Step 3-데이터. 지표 산출 중...")
    metrics = process_trades(raw)

    if metrics.get("total_trades", 0) == 0:
        print(f"\n  [경고] {metrics.get('error')}")
        print("  → 데이터가 부족하거나 미청산 포지션만 존재합니다.")
        print("  → 설문과 AI 분석은 수치 없이 진행됩니다.\n")
    else:
        print(f"\n  총 완결 거래 : {metrics['total_trades']}건")
        print(f"  승률          : {metrics['win_rate']}%")
        print(f"  손익비        : {metrics['rr_ratio']} : 1")
        print(f"  MDD           : {metrics['mdd']:,.0f}원")

    # ── Step 3(설문): 설문지 ──────────────────────────────────────
    survey = run_survey()

    # ── Step 4: AI 융합 분석 ──────────────────────────────────────
    bar("Step 4. AI 융합 분석 중...")
    print("  OpenAI GPT-4o에 분석 요청 중...\n")

    try:
        analysis, score, tier = ai_analyze(metrics, survey, openai_key)
    except Exception as e:
        print(f"  [오류] OpenAI 호출 실패: {e}")
        sys.exit(1)

    # ── Step 5: 결과 출력 ─────────────────────────────────────────
    bar("최종 진단 결과")
    print(f"\n  ★ 등급 : [{tier}]  |  점수 : {score} / 100\n")
    print("─" * 62)
    print(analysis)
    print("─" * 62)

    # ── 결과 저장 (선택) ──────────────────────────────────────────
    save = input("\n  결과를 result.txt로 저장하시겠습니까? (y/n) : ").strip().lower()
    if save == "y":
        with open("result.txt", "w", encoding="utf-8") as f:
            f.write(f"ORION 투자 진단 결과\n생성일: {datetime.now():%Y-%m-%d %H:%M}\n\n")
            f.write(f"등급: {tier}  |  점수: {score}/100\n\n")
            f.write("=== 매매 지표 ===\n")
            for k, v in metrics.items():
                f.write(f"{k}: {v}\n")
            f.write("\n=== AI 분석 ===\n")
            f.write(analysis)
        print("  → result.txt 저장 완료\n")


if __name__ == "__main__":
    main()
