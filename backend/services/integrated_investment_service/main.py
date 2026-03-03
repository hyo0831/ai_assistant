"""
William O'Neil CAN SLIM 기본적 분석 모드
순수 펀더멘털 분석 — 차트/패턴/피봇포인트 없음
"""

import sys
import os

# src 패키지 임포트를 위해 현재 디렉토리를 작업 디렉토리로 설정
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from src.analyzer import run_analysis
from src.ai_client import analyze_fundamentals_with_gemini
from src.result_manager import save_result
from src.utils import format_large_number, format_price


def _print_summary_dashboard(result: dict):
    """CAN SLIM 데이터 요약 대시보드 출력"""
    ticker = result['ticker']
    currency = result.get('currency', 'USD')
    company = result.get('company_name', '')
    data = result.get('data', {})

    print("=" * 60)
    print(f"  CAN SLIM 데이터 요약 — {ticker}")
    if company:
        print(f"  {company} | 통화: {currency}")
    print("=" * 60)

    # C - 분기 실적
    c = data.get('C', {})
    quarters = c.get('quarterly_earnings', [])
    if quarters:
        latest = quarters[0]
        eps = latest.get('eps')
        yoy = latest.get('yoy_growth')
        q_label = latest.get('quarter', '?')
        eps_str = f"{eps:,.0f}" if currency == 'KRW' and eps else f"{eps}" if eps else "N/A"
        yoy_str = f"{yoy:+.0f}%" if yoy is not None else "N/A"
        print(f"  [C] 최근 분기 EPS ({q_label}): {eps_str} (YoY {yoy_str})")
    else:
        print(f"  [C] 분기 EPS 데이터 없음")

    # A - 연간 실적
    a = data.get('A', {})
    annual = a.get('annual_earnings', [])
    if annual:
        latest_a = annual[0]
        eps_a = latest_a.get('eps')
        yoy_a = latest_a.get('yoy_growth')
        yr = latest_a.get('year', '?')
        eps_a_str = f"{eps_a}" if eps_a else "N/A"
        yoy_a_str = f"{yoy_a:+.0f}%" if yoy_a is not None else "N/A"
        print(f"  [A] 최근 연간 EPS ({yr}): {eps_a_str} (YoY {yoy_a_str})")
        roe = a.get('roe')
        if roe is not None:
            print(f"      ROE: {roe}%")
    else:
        print(f"  [A] 연간 EPS 데이터 없음")

    # N - 신촉매
    n = data.get('N', {})
    catalyst_count = len(n.get('catalysts', []))
    hi52 = n.get('near_52w_high')
    hi_str = "Yes" if hi52 else "No"
    print(f"  [N] 촉매 뉴스: {catalyst_count}건 | 52주 신고가 근접: {hi_str}")

    # S - 수급
    s = data.get('S', {})
    mcap = s.get('market_cap')
    if mcap:
        mcap_str = format_large_number(mcap, currency)
        label = s.get('market_cap_label', '')
        print(f"  [S] 시총: {mcap_str} ({label})", end="")
    else:
        print(f"  [S] 시총: N/A", end="")
    dte = s.get('debt_to_equity')
    if dte is not None:
        print(f" | D/E: {dte}%", end="")
    buyback = s.get('buyback_detected')
    if buyback:
        print(f" | 자사주매입 감지", end="")
    print()

    # L - 리더/래거드
    l = data.get('L', {})
    rs = l.get('rs_rating')
    if rs is not None:
        bm = l.get('benchmark', 'Market')
        trend = l.get('rs_trend', 'N/A')
        print(f"  [L] RS Rating: {rs}/99 (vs {bm}) | 추세: {trend}")
    else:
        print(f"  [L] RS Rating: 계산 불가")

    # I - 기관
    i = data.get('I', {})
    inst_pct = i.get('inst_holders_pct')
    inst_cnt = i.get('inst_holders_count')
    if inst_pct is not None:
        print(f"  [I] 기관 보유: {inst_pct}%", end="")
        if inst_cnt:
            print(f" | {inst_cnt}개 기관", end="")
        print()
    else:
        note = i.get('data_note', '')
        print(f"  [I] 기관 데이터: {'제한적' if note else 'N/A'}")

    # M - 시장 방향
    m = data.get('M', {})
    for idx_key in ['sp500', 'nasdaq', 'kospi', 'kosdaq']:
        idx = m.get(idx_key, {})
        if not idx or not idx.get('current_price'):
            continue
        name = idx.get('name', idx_key)
        trend = idx.get('trend', 'N/A')
        dist = idx.get('distribution_days_5wk', 0)
        print(f"  [M] {name}: {trend} | Distribution Days: {dist}")

    print("=" * 60)
    print()


def main():
    print("=" * 60)
    print("  WILLIAM O'NEIL CAN SLIM 기본적 분석 모드")
    print("  (Fundamental Analysis Mode)")
    print("=" * 60)
    print()

    # 종목 코드 입력
    if len(sys.argv) > 1:
        ticker = sys.argv[1].strip().upper()
    else:
        ticker = input("  종목 코드 입력 (e.g., AAPL / 005930.KS): ").strip().upper()

    if not ticker:
        print("[ERROR] 종목 코드를 입력해주세요.")
        return

    print()
    print("=" * 60)
    print(f"  분석 대상: {ticker}")
    print(f"  분석 유형: CAN SLIM 기본적 분석 (펀더멘털 전용)")
    print("=" * 60)

    # 1. CAN SLIM 데이터 수집
    fundamental_result = run_analysis(ticker)

    if fundamental_result.get('error'):
        print(f"\n[ERROR] 데이터 수집 실패: {fundamental_result['error']}")
        return

    # 2. 데이터 요약 대시보드
    _print_summary_dashboard(fundamental_result)

    # 3. Gemini AI 분석
    analysis = analyze_fundamentals_with_gemini(ticker, fundamental_result['prompt_text'])

    # 4. 결과 출력
    print("=" * 60)
    print("  AI 분석 결과 (ANALYSIS RESULT)")
    print("=" * 60)
    print()
    print(analysis)

    # 5. 결과 저장
    print()
    save_result(ticker, analysis, fundamental_result.get('data'))


if __name__ == "__main__":
    main()
