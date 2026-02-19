"""
S - Supply and Demand

데이터 수집에 집중. 점수 없이 AI가 판단할 근거만 제공.
개선: Float 분류, 부채 해석, Accumulation/Distribution, 현금흐름 자사주매입
"""

import pandas as pd
from typing import Dict

ONEIL_RULE = """
### S — Supply and Demand (O'Neil 원문 규칙)
- Smaller-cap stocks (fewer shares outstanding) can move faster, but with greater risk on both sides
- Companies where top management owns a large percentage of stock (at least 1-3% in large companies, more in small) are preferred
- Stock buybacks are positive — a 10% buyback is considered significant
- Lower debt-to-equity ratio is generally better; prefer companies reducing debt over 2-3 years
- Convertible bonds can dilute shares when converted — check for hidden supply
- Volume is the key measure of supply and demand:
  - When stock pulls back: volume should dry up (supply exhausted)
  - When stock rallies: volume should rise (demand absorbing supply)
  - Breakout volume must be at least 40-50% above normal
- Thin float stocks (few shares available) can make explosive moves but are also more volatile
- Excessive stock splits (3-for-1, 5-for-1) increase supply and attract institutional selling — only 18% of big winners split in the year before their major advance
- Avoid stocks near or after excessive splits, especially late in a bull market
""".strip()


def analyze(stock, info: dict) -> Dict:
    """수급 관련 데이터 수집"""
    result = {
        # 시가총액 & 주식수
        'market_cap': None,
        'market_cap_label': '',
        'shares_outstanding': None,
        'float_shares': None,
        'float_pct': None,          # float / shares_outstanding (%)
        'float_label': '',          # Thin / Normal / Large / Very Large
        # 내부자 & 재무
        'insider_pct': None,
        'debt_to_equity': None,
        'debt_level': '',           # Low / Moderate / High / Dangerous
        'current_ratio': None,
        # 자사주 매입
        'buyback_detected': False,
        'buyback_source': '',       # 'cashflow' | 'balance_sheet'
        'share_change_pct': None,
        # Accumulation / Distribution (최근 13주)
        'acc_weeks': None,
        'dist_weeks': None,
        'ad_signal': '',            # ACCUMULATION / DISTRIBUTION / NEUTRAL
        # 주식분할
        'recent_splits': [],
        'excessive_split': False,
        # 부채 추세
        'debt_trend': [],           # [최근, 1년전, 2년전] D/E %
        'debt_decreasing': None,
        # 전환사채
        'has_convertible_debt': False,
        'convertible_debt_amount': None,
        'data_note': ''
    }

    try:
        # 시가총액
        mcap = info.get('marketCap')
        if mcap:
            result['market_cap'] = mcap
            if mcap >= 10e9:
                result['market_cap_label'] = 'Large Cap'
            elif mcap >= 2e9:
                result['market_cap_label'] = 'Mid Cap'
            else:
                result['market_cap_label'] = 'Small Cap'

        # 발행주식수 & 플로트
        shares = info.get('sharesOutstanding')
        if shares:
            result['shares_outstanding'] = shares

        float_shares = info.get('floatShares')
        if float_shares:
            result['float_shares'] = float_shares
            # 플로트 분류 (O'Neil: thin float = 빠른 가격 이동 가능)
            float_m = float_shares / 1e6
            if float_m < 10:
                result['float_label'] = 'Thin (<10M) — can make explosive moves'
            elif float_m < 50:
                result['float_label'] = 'Normal (10M-50M)'
            elif float_m < 200:
                result['float_label'] = 'Large (50M-200M)'
            else:
                result['float_label'] = 'Very Large (>200M) — needs massive buying to move'

            if shares and shares > 0:
                result['float_pct'] = round((float_shares / shares) * 100, 1)

        # 내부자 지분율
        insider_pct = info.get('heldPercentInsiders')
        if insider_pct is not None:
            result['insider_pct'] = round(float(insider_pct * 100), 1)

        # 부채비율 + 해석
        dte = info.get('debtToEquity')
        if dte is not None:
            result['debt_to_equity'] = round(float(dte), 1)
            if dte <= 30:
                result['debt_level'] = 'Low (very conservative)'
            elif dte <= 100:
                result['debt_level'] = 'Moderate'
            elif dte <= 200:
                result['debt_level'] = 'High (caution)'
            else:
                result['debt_level'] = 'Dangerous (>200%)'

        # Current Ratio (재무건전성)
        cr = info.get('currentRatio')
        if cr is not None:
            result['current_ratio'] = round(float(cr), 2)

        # 자사주 매입 — 현금흐름표 우선 (더 신뢰성 높음)
        try:
            cf = stock.quarterly_cashflow
            if cf is not None and not cf.empty:
                buyback_keys = [
                    'Repurchase Of Capital Stock',
                    'Common Stock Repurchased',
                    'Repurchase of Common Stock',
                    'Purchase Of Business',  # fallback
                ]
                for key in buyback_keys:
                    if key in cf.index:
                        recent_val = cf.loc[key].iloc[0]
                        if pd.notna(recent_val) and recent_val < 0:
                            result['buyback_detected'] = True
                            result['buyback_source'] = 'cashflow'
                            break
        except Exception:
            pass

        # 자사주 매입 — 잔액표 fallback (발행주식수 변화)
        if not result['buyback_detected']:
            try:
                bs = stock.quarterly_balance_sheet
                if bs is not None and not bs.empty:
                    shares_key = None
                    for key in ['Ordinary Shares Number', 'Share Issued', 'Common Stock']:
                        if key in bs.index:
                            shares_key = key
                            break
                    if shares_key and bs.shape[1] >= 4:
                        recent = bs.loc[shares_key].iloc[0]
                        older = bs.loc[shares_key].iloc[3]
                        if pd.notna(recent) and pd.notna(older) and older > 0:
                            change_pct = ((recent - older) / older) * 100
                            result['share_change_pct'] = round(float(change_pct), 1)
                            if change_pct <= -2:
                                result['buyback_detected'] = True
                                result['buyback_source'] = 'balance_sheet'
            except Exception:
                pass

        # 주식분할 이력 (과도한 분할 경고)
        try:
            splits = stock.splits
            if splits is not None and not splits.empty:
                import datetime
                two_years_ago = pd.Timestamp.now(tz='UTC') - pd.DateOffset(years=2)
                recent_splits = splits[splits.index >= two_years_ago]
                if not recent_splits.empty:
                    result['recent_splits'] = [
                        {'date': str(idx.date()), 'ratio': float(ratio)}
                        for idx, ratio in recent_splits.items()
                    ]
                    max_ratio = float(recent_splits.max())
                    result['excessive_split'] = max_ratio >= 3.0   # 3:1 이상 = 과도한 분할
                else:
                    result['recent_splits'] = []
                    result['excessive_split'] = False
        except Exception:
            pass

        # 부채 추세 (연간 D/E 변화 — 감소 여부 확인)
        try:
            annual_bs = stock.balance_sheet   # 연간 잔액표 (최근 4년)
            if annual_bs is not None and not annual_bs.empty and annual_bs.shape[1] >= 2:
                debt_keys = ['Total Debt', 'Long Term Debt', 'Net Debt']
                equity_keys = ['Stockholders Equity', 'Total Equity Gross Minority Interest', 'Common Stock Equity']

                debt_vals, equity_vals = [], []
                for key in debt_keys:
                    if key in annual_bs.index:
                        debt_vals = annual_bs.loc[key].dropna().values
                        break
                for key in equity_keys:
                    if key in annual_bs.index:
                        equity_vals = annual_bs.loc[key].dropna().values
                        break

                if len(debt_vals) >= 2 and len(equity_vals) >= 2:
                    n = min(len(debt_vals), len(equity_vals))
                    dte_series = [
                        round((debt_vals[i] / equity_vals[i]) * 100, 1)
                        for i in range(n)
                        if equity_vals[i] != 0
                    ]
                    if len(dte_series) >= 2:
                        result['debt_trend'] = dte_series   # [최근, 1년전, 2년전, ...]
                        result['debt_decreasing'] = dte_series[0] < dte_series[-1]
        except Exception:
            pass

        # 전환사채 (희석 리스크)
        try:
            annual_bs = stock.balance_sheet
            if annual_bs is not None and not annual_bs.empty:
                conv_keys = ['Convertible Debt', 'Long Term Debt And Capital Lease Obligation']
                for key in conv_keys:
                    if key in annual_bs.index:
                        val = annual_bs.loc[key].iloc[0]
                        if pd.notna(val) and val > 0:
                            result['has_convertible_debt'] = True
                            result['convertible_debt_amount'] = float(val)
                            break
        except Exception:
            pass

        # Accumulation / Distribution (최근 13주 주봉)
        try:
            hist = stock.history(period="3mo", interval="1wk")
            if hist is not None and len(hist) >= 5:
                avg_vol = hist['Volume'].mean()
                acc, dist = 0, 0
                for i in range(1, len(hist)):
                    price_chg = hist['Close'].iloc[i] - hist['Close'].iloc[i - 1]
                    vol = hist['Volume'].iloc[i]
                    if pd.isna(vol) or avg_vol == 0:
                        continue
                    if price_chg > 0 and vol > avg_vol:
                        acc += 1
                    elif price_chg < 0 and vol > avg_vol:
                        dist += 1

                result['acc_weeks'] = acc
                result['dist_weeks'] = dist
                if acc > dist + 2:
                    result['ad_signal'] = 'ACCUMULATION'
                elif dist > acc + 2:
                    result['ad_signal'] = 'DISTRIBUTION'
                else:
                    result['ad_signal'] = 'NEUTRAL'
        except Exception:
            pass

    except Exception as e:
        result['data_note'] = f'Error: {e}'

    return result


def format_for_prompt(data: Dict) -> str:
    """AI 프롬프트에 삽입할 텍스트 생성"""
    lines = ["### S - Supply and Demand"]

    # 시가총액
    mcap = data.get('market_cap')
    if mcap and data.get('market_cap_label'):
        cap_str = f"${mcap/1e9:.1f}B" if mcap >= 1e9 else f"${mcap/1e6:.0f}M"
        lines.append(f"Market Cap: {data['market_cap_label']} ({cap_str})")

    # 주식수 & 플로트
    if data.get('shares_outstanding'):
        lines.append(f"Shares Outstanding: {data['shares_outstanding']/1e6:.0f}M")
    if data.get('float_shares'):
        float_m = data['float_shares'] / 1e6
        float_line = f"Float: {float_m:.0f}M shares"
        if data.get('float_pct') is not None:
            float_line += f" ({data['float_pct']}% of outstanding)"
        if data.get('float_label'):
            float_line += f"  ← {data['float_label']}"
        lines.append(float_line)

    # 내부자 지분 (O'Neil 기준: 대형주 1~3%+, 소형주 더 높게)
    if data.get('insider_pct') is not None:
        insider = data['insider_pct']
        mcap = data.get('market_cap') or 0
        insider_line = f"Insider Ownership: {insider}%"
        if mcap >= 10e9:    # 대형주: 1~3% 이상이면 OK
            if insider >= 5:
                insider_line += "  (HIGH for large cap — very bullish)"
            elif insider >= 1:
                insider_line += "  (meets O'Neil minimum for large cap)"
            else:
                insider_line += "  (LOW for large cap — below O'Neil 1% threshold)"
        else:               # 중소형주: 더 높은 기준
            if insider >= 20:
                insider_line += "  (HIGH — strong founder/management alignment)"
            elif insider >= 5:
                insider_line += "  (meaningful for mid/small cap)"
            else:
                insider_line += "  (low — management has limited skin in the game)"
        lines.append(insider_line)

    # 부채비율 + 추세
    if data.get('debt_to_equity') is not None:
        dte_line = f"Debt-to-Equity: {data['debt_to_equity']}%"
        if data.get('debt_level'):
            dte_line += f"  ({data['debt_level']})"
        lines.append(dte_line)

    debt_trend = data.get('debt_trend', [])
    if len(debt_trend) >= 2:
        trend_str = " → ".join(f"{v:.0f}%" for v in debt_trend)
        if data.get('debt_decreasing'):
            lines.append(f"Debt Trend (recent→oldest): {trend_str}  ← DECREASING (O'Neil positive)")
        else:
            lines.append(f"Debt Trend (recent→oldest): {trend_str}  ← INCREASING (caution)")

    # Current Ratio
    if data.get('current_ratio') is not None:
        cr = data['current_ratio']
        cr_line = f"Current Ratio: {cr}"
        if cr >= 2.0:
            cr_line += "  (strong liquidity)"
        elif cr >= 1.0:
            cr_line += "  (adequate)"
        else:
            cr_line += "  (WARNING: below 1.0)"
        lines.append(cr_line)

    # 자사주 매입
    if data.get('share_change_pct') is not None:
        chg = data['share_change_pct']
        if chg <= -5:
            lines.append(f"Share Count Change (1yr): {chg:+.1f}%  (SIGNIFICANT BUYBACK — O'Neil positive)")
        elif chg <= -2:
            lines.append(f"Share Count Change (1yr): {chg:+.1f}%  (buyback detected)")
        elif chg >= 5:
            lines.append(f"Share Count Change (1yr): {chg:+.1f}%  (DILUTION WARNING)")
        else:
            lines.append(f"Share Count Change (1yr): {chg:+.1f}%")

    if data.get('buyback_detected'):
        src = data.get('buyback_source', '')
        lines.append(f"Buyback: Active repurchase confirmed ({src})")

    # 전환사채
    if data.get('has_convertible_debt'):
        amt = data.get('convertible_debt_amount', 0)
        amt_str = f"${amt/1e9:.1f}B" if amt >= 1e9 else f"${amt/1e6:.0f}M"
        lines.append(f"Convertible Debt: {amt_str}  (potential dilution risk when converted)")

    # 주식분할 이력
    splits = data.get('recent_splits', [])
    if splits:
        for s in splits:
            ratio = s['ratio']
            date = s['date']
            if data.get('excessive_split'):
                lines.append(f"Stock Split: {ratio:.0f}-for-1 on {date}  ← EXCESSIVE SPLIT WARNING (increases supply)")
            else:
                lines.append(f"Stock Split: {ratio:.0f}-for-1 on {date}  (moderate — acceptable)")
    elif data.get('recent_splits') is not None:
        lines.append("Stock Split: None in past 2 years  (positive — no artificial supply increase)")

    # Accumulation / Distribution
    acc = data.get('acc_weeks')
    dist = data.get('dist_weeks')
    ad = data.get('ad_signal')
    if acc is not None and dist is not None:
        ad_line = f"Accumulation/Distribution (13wk): {acc}A / {dist}D weeks"
        if ad == 'ACCUMULATION':
            ad_line += "  → ACCUMULATION (institutional buying)"
        elif ad == 'DISTRIBUTION':
            ad_line += "  → DISTRIBUTION (institutional selling — CAUTION)"
        else:
            ad_line += "  → NEUTRAL"
        lines.append(ad_line)

    if data.get('data_note'):
        lines.append(f"Note: {data['data_note']}")

    lines.append("")
    lines.append(ONEIL_RULE)

    return "\n".join(lines)
