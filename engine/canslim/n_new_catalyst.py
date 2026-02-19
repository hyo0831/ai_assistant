"""
N - New Products, New Management, New Highs

AI가 Google Search로 해당 기업의 신제품/서비스/경영 변화를 실시간 조사.
52주 고가 + 역사적 신고가(ATH) 데이터는 코드에서 수집.
"""

import os
import re
import json
from typing import Dict, Optional

# O'Neil 원문 (RAG 참조용)
ONEIL_RULE = """
### N — New Products, New Management, New Highs off Properly Formed Bases (O'Neil 원문 규칙)
- 95%+ of great stock winners had something "new" driving their advance
- This can be: a revolutionary new product/service, a change of management, new industry conditions
- Historical examples: Northern Pacific (railroad), RCA (radio), Syntex (birth control pill),
  McDonald's (fast food), Microsoft (Windows), Cisco (routers), Apple (iPod), Google (search)
- The "Great Paradox": What seems too high and risky usually goes higher; what seems low and cheap usually goes lower
- Stocks on the new-high list tend to go higher; stocks on the new-low list tend to go lower
- Buy when a stock is making new price highs as it breaks out of a proper base on increased volume
- All-time highs are the most powerful — a stock clearing ATH has NO overhead resistance
""".strip()


def analyze(stock, info: dict) -> Dict:
    """52주 고가 + 역사적 신고가(ATH) + AI Google Search 촉매 분석"""
    result = {
        # 52주 가격
        'fifty_two_week_high': None,
        'fifty_two_week_low': None,
        'current_price': None,
        'pct_from_52w_high': None,
        'fifty_two_week_return': None,
        'near_52w_high': False,
        # 역사적 신고가 (ATH)
        'all_time_high': None,
        'pct_from_ath': None,
        'at_all_time_high': False,      # ATH 3% 이내
        'above_all_time_high': False,   # ATH 돌파
        # 거래량
        'volume_ratio': None,
        'breakout_volume_surge': False,
        # AI 촉매
        'ai_catalyst': None,
        'data_note': ''
    }

    try:
        high_52 = info.get('fiftyTwoWeekHigh')
        low_52 = info.get('fiftyTwoWeekLow')
        current = info.get('currentPrice') or info.get('regularMarketPrice')
        company_name = info.get('shortName') or info.get('longName') or ''

        if high_52:
            result['fifty_two_week_high'] = round(float(high_52), 2)
        if low_52:
            result['fifty_two_week_low'] = round(float(low_52), 2)
        if current:
            result['current_price'] = round(float(current), 2)

        if high_52 and current and high_52 > 0:
            result['pct_from_52w_high'] = round(((current - high_52) / high_52) * 100, 1)
            result['near_52w_high'] = result['pct_from_52w_high'] >= -5

        if low_52 and current and low_52 > 0:
            result['fifty_two_week_return'] = round(((current - low_52) / low_52) * 100, 1)

        # 역사적 신고가 (ATH) 계산
        try:
            print("  [*] Fetching all-time high data...")
            hist = stock.history(period="max")
            if not hist.empty and current:
                ath = float(hist['High'].max())
                result['all_time_high'] = round(ath, 2)
                pct_from_ath = ((float(current) - ath) / ath) * 100
                result['pct_from_ath'] = round(pct_from_ath, 1)
                result['at_all_time_high'] = pct_from_ath >= -3    # ATH 3% 이내
                result['above_all_time_high'] = pct_from_ath >= 0  # ATH 실제 돌파
                if result['at_all_time_high']:
                    print(f"  [!!!] AT/NEAR ALL-TIME HIGH ({pct_from_ath:+.1f}%)")
        except Exception as e:
            result['data_note'] += f' ATH fetch error: {e}'

        # 거래량 급증 체크 (현재 거래량 vs 10일 평균)
        try:
            current_vol = info.get('volume') or info.get('regularMarketVolume')
            avg_vol = info.get('averageVolume') or info.get('averageDailyVolume10Day')
            if current_vol and avg_vol and float(avg_vol) > 0:
                vol_ratio = float(current_vol) / float(avg_vol)
                result['volume_ratio'] = round(vol_ratio, 2)
                result['breakout_volume_surge'] = vol_ratio >= 1.5  # 50%+ 급증
        except Exception:
            pass

        # AI Google Search 촉매 조사
        ai_result = _query_ai_for_catalyst(stock.ticker, company_name)
        if ai_result:
            result['ai_catalyst'] = ai_result

    except Exception as e:
        result['data_note'] = f'Error: {e}'

    return result


def _query_ai_for_catalyst(ticker: str, company_name: str) -> Optional[Dict]:
    """Gemini + Google Search로 최신 신제품/신경영 촉매 실시간 조사"""
    try:
        from google import genai
        from google.genai import types

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return None

        client = genai.Client(api_key=api_key)

        prompt = f"""Search Google for the latest information about "{company_name}" (ticker: {ticker}) and analyze O'Neil's "N" (New) factor.

Find RECENT, FACTUAL information about:
1. NEW products, services, or technologies launched or announced in the past 12 months
2. NEW management changes (CEO, CFO, key executives) in the past 12 months
3. NEW industry conditions, regulations, or trends that benefit this company
4. Whether these new factors are visibly driving revenue or earnings growth
5. MANAGEMENT TYPE: Is this company founder-led or entrepreneur-driven (like early Microsoft, Apple, Google)?
   Or is it run by professional "caretaker" managers at a large bureaucratic corporation?
   O'Neil found that founder-led and entrepreneurial companies produce the greatest stock winners.

Respond ONLY with a valid JSON object — no markdown, no explanation outside JSON:
{{
  "new_products": ["<specific product/service with launch date if known>", ...],
  "new_management": ["<name, role, date>", ...],
  "new_industry_trends": ["<trend>", ...],
  "catalyst_summary": "<2-3 sentence factual summary of the most significant N factor>",
  "catalyst_strength": "HIGH or MEDIUM or LOW or NONE",
  "catalyst_strength_reason": "<one sentence explaining the strength rating>",
  "is_founder_led": true or false,
  "management_type": "FOUNDER_LED or ENTREPRENEUR_DRIVEN or PROFESSIONAL_MANAGER or UNKNOWN",
  "management_note": "<one sentence: who leads, since when, founder still involved?>"
}}

catalyst_strength rating criteria:
- HIGH: Game-changing innovation with clear explosive revenue impact (e.g., iPhone launch, ChatGPT, GLP-1 drugs)
- MEDIUM: Meaningful new product/service with measurable revenue contribution
- LOW: Incremental updates, minor new features, or unclear revenue impact
- NONE: No meaningful new catalyst identified in the past 12 months"""

        print(f"  [*] AI (Google Search) researching 'New' catalysts for {ticker}...")
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())]
            )
        )

        text = response.text.strip()

        # JSON 추출 (마크다운 코드블록 및 불필요한 텍스트 제거)
        json_match = re.search(r'\{[\s\S]*\}', text)
        if not json_match:
            return None
        text = json_match.group(0)

        result = json.loads(text)
        strength = result.get('catalyst_strength', '?')
        print(f"  [OK] Catalyst research complete — strength: {strength}")
        return result

    except Exception as e:
        print(f"  [WARNING] AI catalyst research failed: {e}")
        return None


def format_for_prompt(data: Dict) -> str:
    """AI 프롬프트에 삽입할 텍스트 생성"""
    lines = ["### N - New Products, New Management, New Highs"]

    # 현재가 & 52주 데이터
    if data.get('current_price'):
        lines.append(f"Current Price: ${data['current_price']}")
    if data.get('fifty_two_week_high'):
        lines.append(f"52-Week High: ${data['fifty_two_week_high']}")
    if data.get('fifty_two_week_low'):
        lines.append(f"52-Week Low: ${data['fifty_two_week_low']}")
    if data.get('pct_from_52w_high') is not None:
        lines.append(f"Distance from 52W High: {data['pct_from_52w_high']:+.1f}%")
    if data.get('fifty_two_week_return') is not None:
        lines.append(f"52W Return (from low): {data['fifty_two_week_return']:+.1f}%")

    # 역사적 신고가 (ATH) — O'Neil이 가장 중요하게 봄
    if data.get('all_time_high'):
        lines.append(f"All-Time High (ATH): ${data['all_time_high']}")
    if data.get('pct_from_ath') is not None:
        lines.append(f"Distance from ATH: {data['pct_from_ath']:+.1f}%")

    if data.get('above_all_time_high'):
        lines.append("*** ABOVE ALL-TIME HIGH — NO OVERHEAD RESISTANCE. STRONGEST BULLISH SIGNAL. ***")
    elif data.get('at_all_time_high'):
        lines.append("** NEAR ALL-TIME HIGH (within 3%) — Major resistance zone. Watch for volume-confirmed breakout. **")
    elif data.get('near_52w_high'):
        lines.append("Status: NEAR 52-WEEK HIGH")

    # 거래량 급증
    if data.get('volume_ratio') is not None:
        vol_ratio = data['volume_ratio']
        vol_line = f"Volume vs Average: {vol_ratio:.1f}x"
        if data.get('breakout_volume_surge'):
            vol_line += "  ← VOLUME SURGE (breakout confirmation)"
        lines.append(vol_line)

    # AI 촉매 분석 (Google Search 결과)
    ai = data.get('ai_catalyst')
    if ai:
        lines.append("")
        lines.append("AI-Researched Catalysts (via Google Search):")

        strength = ai.get('catalyst_strength', 'UNKNOWN')
        strength_reason = ai.get('catalyst_strength_reason', '')
        lines.append(f"  Catalyst Strength: {strength}")
        if strength_reason:
            lines.append(f"  Reason: {strength_reason}")

        if ai.get('new_products'):
            lines.append(f"  New Products/Services: {'; '.join(ai['new_products'])}")
        if ai.get('new_management'):
            lines.append(f"  New Management: {'; '.join(ai['new_management'])}")
        if ai.get('new_industry_trends'):
            lines.append(f"  Industry Trends: {'; '.join(ai['new_industry_trends'])}")
        if ai.get('catalyst_summary'):
            lines.append(f"  Summary: {ai['catalyst_summary']}")

        # 경영진 타입 (O'Neil: 창업가형 경영진 선호)
        mgmt_type = ai.get('management_type', '')
        mgmt_note = ai.get('management_note', '')
        if mgmt_type:
            if mgmt_type in ('FOUNDER_LED', 'ENTREPRENEUR_DRIVEN'):
                lines.append(f"  Management: {mgmt_type} ← O'Neil POSITIVE (founders/entrepreneurs drive the best winners)")
            elif mgmt_type == 'PROFESSIONAL_MANAGER':
                lines.append(f"  Management: PROFESSIONAL_MANAGER — large-company caretaker type (O'Neil: less likely to produce explosive growth)")
            else:
                lines.append(f"  Management: {mgmt_type}")
            if mgmt_note:
                lines.append(f"  Management Note: {mgmt_note}")

        # 하위 호환: 구버전 has_meaningful_catalyst 필드 처리
        if 'has_meaningful_catalyst' in ai and 'catalyst_strength' not in ai:
            legacy = "MEDIUM" if ai['has_meaningful_catalyst'] else "NONE"
            lines.append(f"  Catalyst Strength (legacy): {legacy}")
    else:
        lines.append("")
        lines.append("AI Catalyst Research: unavailable")

    if data.get('data_note'):
        lines.append(f"Note: {data['data_note']}")

    # RAG: O'Neil 규칙 원문
    lines.append("")
    lines.append(ONEIL_RULE)

    return "\n".join(lines)
