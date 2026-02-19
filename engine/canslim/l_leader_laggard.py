"""
L - Leader or Laggard

RS Rating은 pattern_detector.py에서 계산되어 전달됨.
rs_weeks_declining, resilience_pct 등 RS 라인 상세도 pattern_detector에서 계산.
이 모듈은 수집된 데이터를 해석하고, 섹터 ETF 강도만 직접 조회함.
"""

import yfinance as yf
from typing import Dict

ONEIL_RULE = """
### L — Leader or Laggard (O'Neil 원문 규칙)
- Buy the #1 company in its field — best EPS growth, highest ROE, widest margins, strongest sales, most dynamic price action
- "The first one gets the oyster, the second gets the shell." — Carnegie
- Do NOT buy sympathy plays — second-best stocks never perform as well as the real leader
  (Example: Syntex +400% in 1963 while G.D. Searle, the "cheap" alternative, disappointed)
- RS Rating 87 was the average of all big winners before their major advance (1952-2008 study)
  - RS 90+: potential big winner territory
  - RS 80+: minimum acceptable (O'Neil's practical threshold)
  - RS below 70: LAGGARD — never buy
- RS line declining 7+ months OR rapid drop over 4 months → consider selling
- Best growth stocks decline 1.5x–2.5x the market average during corrections (normal)
  - Stock down 35–40%+ from high → WARNING (abnormal weakness)
- After market correction, true leaders break to new highs within first 3–4 weeks of the new rally
- Watch for stocks that RISE on heavy volume on days the market is DOWN — strongest leader signal
  (Example: Control Data +3.5pts on day Dow fell 12pts → went from $62 to $150)
""".strip()

# 섹터 → 대표 ETF 매핑
_SECTOR_ETF = {
    'Technology': 'XLK',
    'Healthcare': 'XLV',
    'Financial Services': 'XLF',
    'Financials': 'XLF',
    'Consumer Cyclical': 'XLY',
    'Consumer Defensive': 'XLP',
    'Industrials': 'XLI',
    'Energy': 'XLE',
    'Utilities': 'XLU',
    'Real Estate': 'XLRE',
    'Basic Materials': 'XLB',
    'Materials': 'XLB',
    'Communication Services': 'XLC',
}


def analyze(info: dict, rs_analysis: dict = None) -> Dict:
    """
    리더/래거드 판단 근거 수집.

    Args:
        info:        yfinance stock.info 딕셔너리 (orchestrator에서 전달)
        rs_analysis: pattern_detector의 RS 분석 결과 (RS Rating, 추세, 라인 상세 포함)
    """
    result = {
        'sector': None,
        'industry': None,
        # RS Rating
        'rs_rating': None,
        'rs_tier': '',              # POTENTIAL_BIG_WINNER / LEADER / ABOVE_AVERAGE / AVERAGE / LAGGARD
        'never_buy_signal': False,  # RS < 70
        'rs_trend': None,
        'rs_new_high': None,
        'rs_vs_benchmark': {},
        'benchmark': None,
        # RS 라인 상세 (pattern_detector에서 계산됨)
        'rs_weeks_declining': None,
        'rs_sell_signal': False,
        'rs_caution': False,
        'resilience_pct': None,
        'strong_on_down_weeks': None,
        'total_down_weeks': None,
        # 섹터 강도
        'sector_etf': None,
        'sector_vs_sp500_13w': None,
        'sector_leading': None,
        # 기타
        'beta': None,
        'pct_from_52w_high': None,
        'excessive_drawdown': False,    # 52주 고점 대비 35%+ 하락
        'data_note': ''
    }

    try:
        result['sector'] = info.get('sector')
        result['industry'] = info.get('industry')

        # Beta (변동성 — 시장 대비 민감도)
        beta = info.get('beta') or info.get('beta3Year')
        if beta is not None:
            result['beta'] = round(float(beta), 2)

        # 52주 고점 대비 현재가 낙폭
        high_52 = info.get('fiftyTwoWeekHigh')
        current = info.get('currentPrice') or info.get('regularMarketPrice')
        if high_52 and current and high_52 > 0:
            pct = round(((float(current) - float(high_52)) / float(high_52)) * 100, 1)
            result['pct_from_52w_high'] = pct
            result['excessive_drawdown'] = pct <= -35   # 35%+ 하락 = 경고

        # RS 분석 결과 통합 (pattern_detector에서 제공)
        if rs_analysis:
            rs = rs_analysis.get('rs_rating')
            result['rs_rating'] = rs
            result['rs_trend'] = rs_analysis.get('rs_trend')
            result['rs_new_high'] = rs_analysis.get('rs_new_high')
            result['rs_vs_benchmark'] = rs_analysis.get('rs_vs_benchmark', rs_analysis.get('rs_vs_sp500', {}))
            result['benchmark'] = rs_analysis.get('benchmark', 'S&P 500')

            # RS 등급 분류 (1952~2008 연구 기반: 대형 수익주 평균 87)
            if rs is not None:
                if rs >= 90:
                    result['rs_tier'] = 'POTENTIAL_BIG_WINNER'
                elif rs >= 80:
                    result['rs_tier'] = 'LEADER'
                elif rs >= 70:
                    result['rs_tier'] = 'ABOVE_AVERAGE'
                elif rs >= 50:
                    result['rs_tier'] = 'AVERAGE'
                else:
                    result['rs_tier'] = 'LAGGARD'
                result['never_buy_signal'] = rs < 70

            # RS 라인 상세 (pattern_detector에서 계산된 값 읽기)
            result['rs_weeks_declining'] = rs_analysis.get('rs_weeks_declining')
            result['rs_sell_signal'] = rs_analysis.get('rs_sell_signal', False)
            result['rs_caution'] = rs_analysis.get('rs_caution', False)
            result['resilience_pct'] = rs_analysis.get('resilience_pct')
            result['strong_on_down_weeks'] = rs_analysis.get('strong_on_down_weeks')
            result['total_down_weeks'] = rs_analysis.get('total_down_weeks')

        # 섹터 ETF 강도 (이 모듈 고유 데이터 — 타 모듈에서 수집하지 않음)
        sector = result['sector']
        etf_ticker = _SECTOR_ETF.get(sector)
        if etf_ticker:
            result['sector_etf'] = etf_ticker
            try:
                etf_df = yf.Ticker(etf_ticker).history(period="3mo", interval="1wk")
                sp_df = yf.Ticker("^GSPC").history(period="3mo", interval="1wk")
                if not etf_df.empty and not sp_df.empty and len(etf_df) >= 5:
                    etf_ret = ((etf_df['Close'].iloc[-1] - etf_df['Close'].iloc[0]) / etf_df['Close'].iloc[0]) * 100
                    sp_ret = ((sp_df['Close'].iloc[-1] - sp_df['Close'].iloc[0]) / sp_df['Close'].iloc[0]) * 100
                    outperf = round(float(etf_ret - sp_ret), 1)
                    result['sector_vs_sp500_13w'] = outperf
                    result['sector_leading'] = outperf > 0
            except Exception:
                pass

    except Exception as e:
        result['data_note'] = f'Error: {e}'

    return result


def format_for_prompt(data: Dict) -> str:
    """AI 프롬프트에 삽입할 텍스트 생성"""
    lines = ["### L - Leader or Laggard"]

    if data.get('sector'):
        lines.append(f"Sector: {data['sector']}")
    if data.get('industry'):
        lines.append(f"Industry: {data['industry']}")

    # 섹터 강도 — "1등 업종의 1등 주식"
    etf = data.get('sector_etf')
    sector_perf = data.get('sector_vs_sp500_13w')
    if etf and sector_perf is not None:
        sector_line = f"Sector ETF ({etf}) vs S&P500 (13wk): {sector_perf:+.1f}%"
        if data.get('sector_leading'):
            sector_line += "  <- SECTOR LEADING (buy leaders of leading sectors)"
        else:
            sector_line += "  <- Sector lagging market"
        lines.append(sector_line)

    # 52주 고점 대비 낙폭
    pct_high = data.get('pct_from_52w_high')
    if pct_high is not None:
        drawdown_line = f"Distance from 52W High: {pct_high:+.1f}%"
        if data.get('excessive_drawdown'):
            drawdown_line += "  <- WARNING: 35%+ drawdown (abnormal weakness)"
        lines.append(drawdown_line)

    # Beta
    if data.get('beta') is not None:
        beta = data['beta']
        beta_line = f"Beta: {beta}"
        if beta >= 1.5:
            beta_line += "  (high volatility -- moves 1.5x+ market)"
        elif beta >= 1.0:
            beta_line += "  (normal growth stock volatility)"
        elif beta < 0.5:
            beta_line += "  (defensive / low volatility)"
        lines.append(beta_line)

    # RS Rating — 핵심
    bm = data.get('benchmark', 'Market')
    rs = data.get('rs_rating')
    tier = data.get('rs_tier', '')
    if rs is not None:
        tier_labels = {
            'POTENTIAL_BIG_WINNER': f"RS {rs}/99  <- POTENTIAL BIG WINNER (90+, study avg was 87)",
            'LEADER':               f"RS {rs}/99  <- LEADER (80+, O'Neil minimum threshold)",
            'ABOVE_AVERAGE':        f"RS {rs}/99  <- Above average, approaching leader territory",
            'AVERAGE':              f"RS {rs}/99  <- Average -- not a leader",
            'LAGGARD':              f"RS {rs}/99  <- LAGGARD",
        }
        lines.append(f"RS Rating (vs {bm}): {tier_labels.get(tier, str(rs))}")

    if data.get('never_buy_signal'):
        lines.append("*** O'Neil WARNING: RS below 70 -- NEVER buy laggards. You want leaders only. ***")

    # RS 추세
    if data.get('rs_trend'):
        trend = data['rs_trend']
        note = {'RISING': '  (RS momentum improving)', 'FALLING': '  (RS losing ground)'}
        lines.append(f"RS Trend (10-week): {trend}{note.get(trend, '')}")

    # RS 라인 연속 하락 주수 (O'Neil 매도 신호)
    weeks_dec = data.get('rs_weeks_declining')
    if weeks_dec is not None:
        months = round(weeks_dec / 4.3, 1)
        rs_line = f"RS Line Declining: {weeks_dec} consecutive weeks (~{months} months)"
        if data.get('rs_sell_signal'):
            rs_line += "  <- SELL SIGNAL (7+ months decline)"
        elif data.get('rs_caution'):
            rs_line += "  <- CAUTION (4+ months decline)"
        lines.append(rs_line)

    if data.get('rs_new_high'):
        lines.append("RS New High: YES -- RS line at 52-week high (RS leading price -- BULLISH)")
    elif data.get('rs_new_high') is False:
        lines.append("RS New High: No")

    # 시장 하락 주 방어력 (이상 강세 감지)
    resilience = data.get('resilience_pct')
    strong_down = data.get('strong_on_down_weeks')
    total_down = data.get('total_down_weeks')
    if resilience is not None and total_down:
        res_line = f"Resilience on Down Weeks: {strong_down}/{total_down} weeks rose when market fell ({resilience}%)"
        if resilience >= 50:
            res_line += "  <- STRONG LEADER SIGNAL (rises against market)"
        elif resilience >= 30:
            res_line += "  (moderate resilience)"
        else:
            res_line += "  (weak -- follows market down)"
        lines.append(res_line)

    # 기간별 성과
    rs_data = data.get('rs_vs_benchmark', {})
    if rs_data:
        def _sort_key(k):
            kl = k.lower()
            try:
                n = int(''.join(filter(str.isdigit, kl)))
                if 'y' in kl: return n * 52
                if 'm' in kl: return n * 4
                return n
            except ValueError:
                return 999

        lines.append(f"Performance vs {bm} (short->long):")
        for period in sorted(rs_data.keys(), key=_sort_key):
            vals = rs_data[period]
            bm_ret = vals.get('benchmark_return', vals.get('sp500_return', 0))
            out = vals['outperformance']
            flag = " [OUTPERFORM]" if out > 0 else " [UNDERPERFORM]"
            lines.append(f"  {period}: Stock {vals['stock_return']:+.1f}% vs {bm} {bm_ret:+.1f}% ({out:+.1f}%){flag}")

    if data.get('data_note'):
        lines.append(f"Note: {data['data_note']}")

    lines.append("")
    lines.append(ONEIL_RULE)

    return "\n".join(lines)
