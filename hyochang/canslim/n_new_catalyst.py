"""
N - New Products, New Management, New Highs

AI가 해당 기업의 신제품/서비스/경영 변화를 직접 조사하여 판단.
52주 가격 데이터는 코드에서 수집, 촉매 분석은 AI에게 위임.
"""

import os
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
""".strip()


def analyze(stock, info: dict) -> Dict:
    """52주 가격 데이터 수집 + AI 촉매 분석"""
    result = {
        'fifty_two_week_high': None,
        'fifty_two_week_low': None,
        'current_price': None,
        'pct_from_52w_high': None,
        'fifty_two_week_return': None,
        'near_52w_high': False,
        'ai_catalyst': None,     # AI 조사 결과
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

        # AI에게 촉매 조사 요청
        ai_result = _query_ai_for_catalyst(stock.ticker, company_name)
        if ai_result:
            result['ai_catalyst'] = ai_result

    except Exception as e:
        result['data_note'] = f'Error: {e}'

    return result


def _query_ai_for_catalyst(ticker: str, company_name: str) -> Optional[Dict]:
    """Gemini AI에게 해당 기업의 최근 신제품/서비스/촉매 조사 요청"""
    try:
        from google import genai

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return None

        client = genai.Client(api_key=api_key)

        prompt = f"""You are analyzing "{company_name}" (ticker: {ticker}) for William O'Neil's "N" (New) factor.

Research this company and provide factual information about:
1. NEW products, services, or technologies launched or announced in the past 12 months
2. NEW management changes (CEO, key executives) in the past 12 months
3. NEW industry conditions or trends that benefit this company
4. Whether these new factors appear to be driving revenue/earnings growth

Respond ONLY with a JSON object:
{{
  "new_products": ["<product/service 1>", "<product/service 2>", ...],
  "new_management": ["<change 1>", ...],
  "new_industry_trends": ["<trend 1>", ...],
  "catalyst_summary": "<2-3 sentence factual summary of the most significant 'New' factor>",
  "has_meaningful_catalyst": true/false
}}"""

        print(f"  [*] AI researching 'New' catalysts for {ticker}...")
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )

        text = response.text.strip()
        if text.startswith('```'):
            text = text.split('\n', 1)[1] if '\n' in text else text[3:]
            if text.endswith('```'):
                text = text[:-3]
            text = text.strip()

        result = json.loads(text)
        print(f"  [OK] Catalyst research complete")
        return result

    except Exception as e:
        print(f"  [WARNING] AI catalyst research failed: {e}")
        return None


def format_for_prompt(data: Dict) -> str:
    """AI 프롬프트에 삽입할 텍스트 생성"""
    lines = ["### N - New Products, New Management, New Highs"]

    # 가격 데이터
    if data.get('current_price'):
        lines.append(f"Current Price: ${data['current_price']}")
    if data.get('fifty_two_week_high'):
        lines.append(f"52-Week High: ${data['fifty_two_week_high']}")
    if data.get('fifty_two_week_low'):
        lines.append(f"52-Week Low: ${data['fifty_two_week_low']}")
    if data.get('pct_from_52w_high') is not None:
        lines.append(f"Distance from 52W High: {data['pct_from_52w_high']:+.1f}%")
    if data.get('fifty_two_week_return') is not None:
        lines.append(f"52-Week Return (from low): {data['fifty_two_week_return']:+.1f}%")
    if data.get('near_52w_high'):
        lines.append("Status: NEAR 52-WEEK HIGH")

    # AI 촉매 분석 결과
    ai = data.get('ai_catalyst')
    if ai:
        lines.append("")
        lines.append("AI-Researched Catalysts:")
        if ai.get('new_products'):
            lines.append(f"  New Products/Services: {'; '.join(ai['new_products'])}")
        if ai.get('new_management'):
            lines.append(f"  New Management: {'; '.join(ai['new_management'])}")
        if ai.get('new_industry_trends'):
            lines.append(f"  Industry Trends: {'; '.join(ai['new_industry_trends'])}")
        if ai.get('catalyst_summary'):
            lines.append(f"  Summary: {ai['catalyst_summary']}")
        if ai.get('has_meaningful_catalyst') is not None:
            lines.append(f"  Has Meaningful Catalyst: {'Yes' if ai['has_meaningful_catalyst'] else 'No'}")

    if data.get('data_note'):
        lines.append(f"Note: {data['data_note']}")

    # RAG: O'Neil 규칙 원문
    lines.append("")
    lines.append(ONEIL_RULE)

    return "\n".join(lines)
