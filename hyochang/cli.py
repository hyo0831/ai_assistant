"""
CLI entry point for William O'Neil AI Investment Assistant
"""
import sys
import re
from datetime import datetime

# Windows cp949 터미널에서 UTF-8 출력 보장
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from core.config import CHART_OUTPUT_PATH
from core.data_fetcher import fetch_stock_data, calculate_moving_averages
from core.chart_generator import create_oneil_chart
from core.ai_analyzer import analyze_chart_with_gemini, analyze_chart_v2
from core.result_manager import save_analysis_result

from core.feedback_manager import FeedbackManager, collect_feedback
from core.pattern_detector import run_pattern_detection
from core.fundamental_analyzer import analyze_fundamentals
from core.version import VERSION


def _print_analysis_result(analysis: str, rs_info: dict = None):
    """분석 결과 출력"""
    print()
    print("=" * 80)
    print("ANALYSIS RESULT / 분석 결과")
    print("=" * 80)

    if rs_info and rs_info.get('rs_rating') is not None:
        print()
        print("-" * 40)
        print(f"  RS Rating: {rs_info['rs_rating']}/99")
        print(f"  RS Trend (10주): {rs_info.get('rs_trend', 'N/A')}")
        print(f"  RS New High: {'Yes' if rs_info.get('rs_new_high') else 'No'}")
        if rs_info.get('interpretation'):
            print(f"  평가: {rs_info['interpretation']}")
        print("-" * 40)

    print()
    print(analysis)
    print()
    print("=" * 80)
    print(f"차트 저장 위치 (Chart saved): {CHART_OUTPUT_PATH}")
    print("=" * 80)


def _collect_and_save_feedback(ticker: str, analysis: str, feedback_manager: FeedbackManager):
    """피드백 수집 및 저장"""
    try:
        verdict_match = re.search(r'"verdict":\s*"([^"]+)"', analysis)
        if not verdict_match:
            verdict_match = re.search(r'(?:FINAL VERDICT|Verdict)[:\s]*(BUY NOW|WATCH & WAIT|AVOID)', analysis)
        verdict = verdict_match.group(1) if verdict_match else "UNKNOWN"
    except Exception:
        verdict = "UNKNOWN"

    feedback_data = collect_feedback(ticker, analysis, verdict)
    if feedback_data:
        feedback_manager.save_feedback(
            ticker=feedback_data["ticker"],
            analysis=feedback_data["analysis"],
            verdict=feedback_data["verdict"],
            rating=feedback_data["rating"],
            comment=feedback_data["comment"]
        )
        print(f"[OK] Feedback saved! AI will learn from it in next analysis.")


def _select_chart_interval() -> tuple:
    """
    차트 간격 선택 (주봉/일봉)

    Returns:
        (interval, period, short_ma, long_ma) 튜플
    """
    print()
    print("  차트 유형 선택 (Chart type):")
    print("  [W] 주봉 Weekly (기본/Default)")
    print("  [D] 일봉 Daily")
    choice = input("  Select (W/D): ").strip().upper()

    if choice == 'D':
        return ('1d', '1y', 50, 200)
    else:
        return ('1wk', '3y', 10, 40)


def main_v1(ticker: str, interval: str = "1wk", period: str = "3y",
            short_ma: int = 10, long_ma: int = 40):
    """
    V1 메인 실행 함수 (기존 버전)
    AI가 차트 이미지를 직접 보고 분석
    """
    chart_type = "Weekly / 주봉" if interval == "1wk" else "Daily / 일봉"
    print("=" * 80)
    print("WILLIAM O'NEIL AI INVESTMENT ASSISTANT [V1 - Basic]")
    print("윌리엄 오닐 AI 투자 어시스턴트 [V1 - 기본 분석]")
    print("=" * 80)
    print(f"분석 종목 (Target): {ticker}")
    print(f"차트 유형 (Chart): {chart_type}")
    print(f"분석 시간 (Timestamp): {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print()

    try:
        df = fetch_stock_data(ticker, period=period, interval=interval)
        df = calculate_moving_averages(df, short_window=short_ma, long_window=long_ma)
        create_oneil_chart(ticker, df, interval=interval)

        feedback_manager = FeedbackManager()
        analysis = analyze_chart_with_gemini(CHART_OUTPUT_PATH, ticker, df, feedback_manager,
                                             interval=interval)

        _print_analysis_result(analysis)
        save_analysis_result(ticker=ticker, analysis=analysis, interval=interval)
        _collect_and_save_feedback(ticker, analysis, feedback_manager)

    except Exception as e:
        print(f"[ERROR] {e}")
        raise


def main_v2(ticker: str, interval: str = "1wk", period: str = "3y",
            short_ma: int = 10, long_ma: int = 40):
    """
    V2 메인 실행 함수 (향상 버전)
    코드 기반 패턴 감지 + 펀더멘털 분석 → AI가 결과를 해석
    """
    chart_type = "Weekly / 주봉" if interval == "1wk" else "Daily / 일봉"
    print("=" * 80)
    print("WILLIAM O'NEIL AI INVESTMENT ASSISTANT [V2 - Enhanced Pattern Detection]")
    print("윌리엄 오닐 AI 투자 어시스턴트 [V2 - 향상된 패턴 감지 + 펀더멘털]")
    print("=" * 80)
    print(f"분석 종목 (Target): {ticker}")
    print(f"차트 유형 (Chart): {chart_type}")
    print(f"분석 시간 (Timestamp): {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print()

    try:
        df = fetch_stock_data(ticker, period=period, interval=interval)
        df = calculate_moving_averages(df, short_window=short_ma, long_window=long_ma)

        print()
        pattern_result = run_pattern_detection(df, ticker)
        print()

        print("-" * 60)
        print("CODE DETECTION PREVIEW:")
        print("-" * 60)
        if pattern_result['best_pattern']:
            bp = pattern_result['best_pattern']
            print(f"  Pattern: {bp['type']}")
            print(f"  Quality: {bp.get('quality_score', 0)}/100")
            print(f"  Pivot Point: ${bp.get('pivot_point', 0):.2f}")
            if pattern_result['pattern_faults']:
                print(f"  Faults: {len(pattern_result['pattern_faults'])}")
                for f in pattern_result['pattern_faults']:
                    print(f"    - {f}")
        else:
            print("  No clear pattern detected")
        print(f"  Base Stage: {pattern_result['base_stage'].get('estimated_stage', 'N/A')}")
        print(f"  Volume Trend: {pattern_result['volume_analysis'].get('recent_volume_trend', 'N/A')}")
        rs = pattern_result.get('rs_analysis', {})
        if rs.get('rs_rating') is not None:
            print(f"  RS Rating: {rs['rs_rating']}/99 | Trend: {rs.get('rs_trend', 'N/A')} | New High: {'Yes' if rs.get('rs_new_high') else 'No'}")
        print("-" * 60)
        print()

        print()
        rs_analysis = pattern_result.get('rs_analysis', {})
        fundamental_result = analyze_fundamentals(ticker, rs_analysis=rs_analysis)
        print()

        pivot_info = None
        best_pattern = pattern_result.get('best_pattern')
        if best_pattern and best_pattern.get('pivot_point'):
            pivot_info = {
                'price': best_pattern['pivot_point'],
                'date': (best_pattern.get('right_peak_date')
                         or best_pattern.get('middle_peak_date')
                         or best_pattern.get('end_date')),
                'pattern_type': best_pattern.get('type', ''),
            }
        create_oneil_chart(ticker, df, interval=interval, pivot_info=pivot_info)

        feedback_manager = FeedbackManager()
        analysis = analyze_chart_v2(
            CHART_OUTPUT_PATH, ticker, df, pattern_result, feedback_manager,
            fundamental_result, interval=interval
        )

        rs_info = pattern_result.get('rs_analysis', {})
        _print_analysis_result(analysis, rs_info=rs_info)

        save_analysis_result(
            ticker=ticker,
            analysis=analysis,
            interval=interval,
            pattern_result=pattern_result,
            fundamental_result=fundamental_result,
            rs_info=rs_info,
        )

        _collect_and_save_feedback(ticker, analysis, feedback_manager)

    except Exception as e:
        print(f"[ERROR] {e}")
        raise


def main_compare(tickers: list):
    """
    다중 종목 비교 모드 - 여러 종목의 핵심 지표를 테이블로 비교
    """
    print("=" * 80)
    print("WILLIAM O'NEIL MULTI-STOCK COMPARISON / 다중 종목 비교")
    print("=" * 80)
    print(f"비교 종목 (Tickers): {', '.join(tickers)}")
    print(f"분석 시간 (Timestamp): {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print()

    results = []

    for ticker in tickers:
        print(f"[*] Analyzing {ticker}...")
        try:
            df = fetch_stock_data(ticker, period="3y", interval="1wk")
            df = calculate_moving_averages(df, short_window=10, long_window=40)

            pattern_result = run_pattern_detection(df, ticker)

            current_price = df.iloc[-1]['Close']
            ma10 = df.iloc[-1]['MA50']
            ma40 = df.iloc[-1]['MA200']

            rs = pattern_result.get('rs_analysis', {})
            bp = pattern_result.get('best_pattern')

            row = {
                'Ticker': ticker,
                'Price': f"${current_price:.2f}",
                'vs 10w MA': f"{((current_price - ma10) / ma10) * 100:+.1f}%",
                'vs 40w MA': f"{((current_price - ma40) / ma40) * 100:+.1f}%",
                'RS Rating': rs.get('rs_rating', 'N/A'),
                'RS Trend': rs.get('rs_trend', 'N/A'),
                'Pattern': bp['type'] if bp else 'None',
                'Quality': f"{bp['quality_score']}/100" if bp else '-',
                'Stage': pattern_result['base_stage'].get('estimated_stage', 'N/A'),
                'Vol Trend': pattern_result['volume_analysis'].get('recent_volume_trend', 'N/A'),
            }
            results.append(row)
            print(f"[OK] {ticker} complete")

        except Exception as e:
            print(f"[ERROR] {ticker}: {e}")
            results.append({'Ticker': ticker, 'Price': 'ERROR', 'vs 10w MA': '-',
                            'vs 40w MA': '-', 'RS Rating': '-', 'RS Trend': '-',
                            'Pattern': '-', 'Quality': '-',
                            'Stage': '-', 'Vol Trend': '-'})

    print()
    print("=" * 120)
    print("COMPARISON TABLE / 비교 결과")
    print("=" * 120)

    if results:
        headers = list(results[0].keys())
        col_widths = {}
        for h in headers:
            col_widths[h] = max(len(str(h)), max(len(str(r.get(h, ''))) for r in results)) + 2

        header_line = " | ".join(str(h).ljust(col_widths[h]) for h in headers)
        print(header_line)
        print("-" * len(header_line))

        for row in results:
            line = " | ".join(str(row.get(h, '')).ljust(col_widths[h]) for h in headers)
            print(line)

    print("=" * 120)
    print()

    ranked = [r for r in results if r.get('RS Rating') not in ('N/A', '-')]
    if ranked:
        ranked.sort(key=lambda x: int(x['RS Rating']) if isinstance(x['RS Rating'], int) else 0, reverse=True)
        print("RS Rating 순위 (Ranking by RS Rating):")
        for i, r in enumerate(ranked, 1):
            print(f"  {i}. {r['Ticker']} - RS {r['RS Rating']}, Pattern: {r['Pattern']}")
        print()


def main():
    """대화형 CLI 메뉴 진입점"""
    print()
    print("=" * 80)
    print(f"  WILLIAM O'NEIL AI INVESTMENT ASSISTANT  v{VERSION}")
    print(f"  윌리엄 오닐 AI 투자 어시스턴트")
    print("=" * 80)
    print()
    print("  [1] V1 - Basic (AI 이미지 분석)")
    print("      AI가 차트 이미지를 직접 보고 분석합니다.")
    print()
    print("  [2] V2 - Enhanced (패턴 감지 + 펀더멘털 + AI 해석)")
    print("      코드가 패턴을 먼저 감지하고, 펀더멘털 분석 후 AI가 종합 해석합니다.")
    print()
    print("  [3] Compare - 다중 종목 비교")
    print("      여러 종목을 비교 분석하여 테이블로 출력합니다.")
    print()
    print("=" * 80)

    mode = input("  모드 선택 (Select mode) [1/2/3]: ").strip()
    if mode not in ('1', '2', '3'):
        print("  잘못된 선택입니다. V2로 기본 설정합니다.")
        mode = '2'

    if mode == '3':
        tickers_input = input("  종목 코드 입력 (쉼표 구분, e.g., AAPL,MSFT,NVDA): ").strip().upper()
        if not tickers_input:
            tickers_input = "AAPL,MSFT,NVDA"
            print(f"  기본값 사용: {tickers_input}")
        tickers = [t.strip() for t in tickers_input.split(',') if t.strip()]
        print()
        main_compare(tickers)
    else:
        ticker = input("  종목 코드 입력 (Enter ticker, e.g., AAPL): ").strip().upper()
        if not ticker:
            ticker = "AAPL"
            print(f"  기본값 사용 (Default): {ticker}")

        interval, period, short_ma, long_ma = _select_chart_interval()
        print()

        if mode == '1':
            main_v1(ticker, interval=interval, period=period,
                    short_ma=short_ma, long_ma=long_ma)
        else:
            main_v2(ticker, interval=interval, period=period,
                    short_ma=short_ma, long_ma=long_ma)


if __name__ == "__main__":
    main()
