import re
from google import genai
from google.genai import types
from PIL import Image
import json

from core.config import GEMINI_API_KEY, LANGUAGE
from core.system_prompt import WILLIAM_ONEIL_ENHANCED_PERSONA


def _get_language_instruction() -> str:
    """분석 프롬프트에 삽입할 언어 지시 생성"""
    if LANGUAGE == "ko":
        return (
            "\n\nIMPORTANT - LANGUAGE INSTRUCTION:\n"
            "You MUST write your entire analysis in Korean (한국어).\n"
            "Keep technical terms in English where appropriate "
            "(e.g., Cup with Handle, CAN SLIM, Flat Base, Double Bottom, "
            "High Tight Flag, RS Rating, EPS, ROE, P/E, Buy Point, Stop Loss, "
            "Accumulation, Distribution, Breakout).\n"
            "All explanatory text, commentary, and conclusions must be in Korean.\n"
        )
    return ""


def _remove_emojis(text: str) -> str:
    """이모지만 선택적으로 제거하고 한국어/일본어/중국어 등 모든 유니코드 문자 보존"""
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U0001F900-\U0001F9FF"  # supplemental symbols
        "\U0001FA00-\U0001FA6F"  # chess symbols
        "\U0001FA70-\U0001FAFF"  # symbols extended-A
        "\U0000FE00-\U0000FE0F"  # variation selectors
        "\U0000200D"             # zero width joiner
        "\U00002B50"             # star
        "\U00002B55"             # circle
        "]+",
        flags=re.UNICODE
    )
    return emoji_pattern.sub('', text)


def analyze_chart_with_gemini(image_path: str, ticker: str, df=None,
                               feedback_manager=None,
                               interval: str = "1wk") -> str:
    """
    Gemini를 사용하여 차트 분석

    Args:
        image_path: 차트 이미지 경로
        ticker: 종목 코드
        df: OHLCV 데이터프레임
        feedback_manager: 피드백 매니저
        interval: 차트 간격 ('1wk' 주봉, '1d' 일봉)

    Returns:
        AI 분석 결과 텍스트
    """
    print(f"[*] Analyzing chart with Gemini (William O'Neil persona)...")

    client = genai.Client(api_key=GEMINI_API_KEY)
    image = Image.open(image_path)

    data_summary = ""
    if df is not None and not df.empty:
        recent_data = df.tail(52)
        max_idx = recent_data['High'].idxmax()
        min_idx = recent_data['Low'].idxmin()
        current_price = df.iloc[-1]['Close']
        current_date = df.index[-1].strftime('%Y-%m-%d')

        data_summary = f"""

IMPORTANT DATA CONTEXT (for accurate date/price reference):
- Current Date: {current_date}
- Current Price: ${current_price:.2f}
- Recent 52-week High: ${recent_data.loc[max_idx, 'High']:.2f} on {max_idx.strftime('%Y-%m-%d')}
- Recent 52-week Low: ${recent_data.loc[min_idx, 'Low']:.2f} on {min_idx.strftime('%Y-%m-%d')}
- Data Period: {df.index[0].strftime('%Y-%m-%d')} to {df.index[-1].strftime('%Y-%m-%d')} ({len(df)} weeks total)
- 10-week MA: ${df.iloc[-1]['MA50']:.2f}
- 40-week MA: ${df.iloc[-1]['MA200']:.2f}

Use these exact dates and prices in your analysis for accuracy.
"""

    feedback_context = ""
    if feedback_manager:
        feedback_context = feedback_manager.get_feedback_context(ticker)

    lang_instruction = _get_language_instruction()

    if interval == '1d':
        chart_type_text = "DAILY"
        timeframe_note = "This is a DAILY chart. Each candle represents one day of trading."
    else:
        chart_type_text = "WEEKLY"
        timeframe_note = "This is a WEEKLY chart, not a daily chart. Each candle represents one week of trading.\nWhen analyzing patterns, use weekly timeframes (e.g., \"Cup with Handle\" should be 7-65 weeks, not days)."

    analysis_prompt = f"""
Analyze this {chart_type_text} stock chart for {ticker}.
{data_summary}
{feedback_context}
{lang_instruction}
IMPORTANT: {timeframe_note}

Provide your analysis in TWO parts:

PART 1: JSON Pattern Data (for chart annotation)
Return a JSON object with pattern details. Include APPROXIMATE week indices (counting from oldest data as 0):
{{
  "pattern_type": "Cup with Handle" | "Double Bottom" | "Flat Base" | "Ascending Base" | "None",
  "key_levels": {{
    "buy_point": <price>,
    "stop_loss": <price>,
    "support": <price>,
    "resistance": <price>
  }},
  "pattern_points": {{
    "pattern_start_week": <week_index>,
    "left_peak_week": <week_index>,
    "bottom_week": <week_index>,
    "right_peak_week": <week_index>,
    "handle_start_week": <week_index or null>,
    "handle_end_week": <week_index or null>,
    "current_week": <week_index>
  }},
  "current_price": <price>,
  "verdict": "BUY NOW" | "WATCH & WAIT" | "AVOID"
}}

Note: For week indices, estimate based on the visible chart. For example, if the pattern started ~40 weeks ago and there are ~150 weeks total, pattern_start_week would be around 110.

PART 2: Detailed Analysis

## CHART ANALYSIS: {ticker}

### 1. Trend Status
[Analyze the primary trend using moving averages]

### 2. Pattern Recognition
[Identify any CAN SLIM patterns present]

### 3. Volume Behavior
[Assess volume characteristics and breakout signals]

### 4. Buy Point & Entry
[Specify exact buy point and current position relative to it]

### 5. Risk Management
[Define stop-loss level and risk/reward ratio]

### 6. FINAL VERDICT
[Your clear, actionable recommendation: BUY NOW / WATCH & WAIT / AVOID]

---
Be specific, use actual price levels visible on the chart, and give your honest professional opinion.
"""

    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[analysis_prompt, image],
        config=types.GenerateContentConfig(
            system_instruction=WILLIAM_ONEIL_ENHANCED_PERSONA,
        )
    )

    print("[OK] Analysis complete!")
    return _remove_emojis(response.text)


def parse_pattern_data(analysis_text: str) -> dict:
    """
    AI 분석 결과에서 JSON 패턴 데이터 추출

    Args:
        analysis_text: AI 분석 텍스트

    Returns:
        패턴 데이터 딕셔너리 (추출 실패 시 None)
    """
    try:
        json_match = re.search(r'```json\s*(.*?)\s*```', analysis_text, re.DOTALL)
        if not json_match:
            json_match = re.search(r'\{[^{}]*"pattern_type"[^{}]*\}', analysis_text, re.DOTALL)

        if json_match:
            json_str = json_match.group(1) if '```' in analysis_text else json_match.group(0)
            pattern_data = json.loads(json_str)
            return pattern_data
    except Exception as e:
        print(f"[WARNING] Could not parse pattern data: {e}")

    return None


def analyze_chart_v2(image_path: str, ticker: str, df,
                     pattern_result: dict,
                     feedback_manager=None,
                     fundamental_result: dict = None,
                     interval: str = "1wk",
                     history_context: str = "") -> str:
    """
    V2: 코드 기반 패턴 감지 결과 + 펀더멘털 분석을 AI에게 전달하여 해석

    Args:
        image_path: 차트 이미지 경로
        ticker: 종목 코드
        df: OHLCV 데이터프레임
        pattern_result: pattern_detector.run_pattern_detection() 결과
        feedback_manager: 피드백 매니저
        fundamental_result: fundamental_analyzer.analyze_fundamentals() 결과
        interval: 차트 간격
        history_context: 과거 분석 히스토리 컨텍스트

    Returns:
        AI 분석 결과 텍스트
    """
    print(f"[*] V2: Analyzing with code-detected patterns + AI interpretation...")

    client = genai.Client(api_key=GEMINI_API_KEY)
    image = Image.open(image_path)

    data_summary = ""
    if df is not None and not df.empty:
        recent_data = df.tail(52)
        max_idx = recent_data['High'].idxmax()
        min_idx = recent_data['Low'].idxmin()
        current_price = df.iloc[-1]['Close']
        current_date = df.index[-1].strftime('%Y-%m-%d')

        data_summary = f"""
IMPORTANT DATA CONTEXT (for accurate date/price reference):
- Current Date: {current_date}
- Current Price: ${current_price:.2f}
- Recent 52-week High: ${recent_data.loc[max_idx, 'High']:.2f} on {max_idx.strftime('%Y-%m-%d')}
- Recent 52-week Low: ${recent_data.loc[min_idx, 'Low']:.2f} on {min_idx.strftime('%Y-%m-%d')}
- Data Period: {df.index[0].strftime('%Y-%m-%d')} to {df.index[-1].strftime('%Y-%m-%d')} ({len(df)} weeks total)
- 10-week MA: ${df.iloc[-1]['MA50']:.2f}
- 40-week MA: ${df.iloc[-1]['MA200']:.2f}
"""

    pattern_summary = pattern_result.get('summary', 'No pattern detection results available.')

    fundamental_summary = ""
    if fundamental_result and not fundamental_result.get('error'):
        fundamental_summary = fundamental_result.get('prompt_text', '')

    feedback_context = ""
    if feedback_manager:
        feedback_context = feedback_manager.get_feedback_context(ticker)

    lang_instruction = _get_language_instruction()

    chart_type_text = "DAILY" if interval == '1d' else "WEEKLY"
    if interval == '1d':
        timeframe_note = "This is a DAILY chart. Each candle = one day of trading."
    else:
        timeframe_note = "This is a WEEKLY chart. Each candle = one week of trading."

    analysis_prompt = f"""
Analyze this {chart_type_text} stock chart for {ticker}.

{data_summary}
{lang_instruction}

## CODE-BASED PATTERN DETECTION RESULTS
The following patterns and metrics were detected by our automated pattern detection engine.
Use these results as quantitative reference data to support your visual analysis of the chart.
If the code detection and your visual analysis conflict, explain the discrepancy.

{pattern_summary}

## CAN SLIM FUNDAMENTAL DATA
The following is factual data collected for each CAN SLIM factor (C, A, N, S, L, I, M).
Each section includes O'Neil's original rules from "How to Make Money in Stocks" for your reference.
Evaluate each factor against O'Neil's criteria based on the data provided.
Do NOT use pre-calculated scores -- make your own judgment based on the raw data and O'Neil's rules.

{fundamental_summary if fundamental_summary else "Fundamental data not available."}

{feedback_context}

IMPORTANT: {timeframe_note}

Based on the chart image, code-detected pattern data, AND CAN SLIM fundamental data above, provide your analysis:

## CHART ANALYSIS: {ticker}

### 1. Trend Status
[Analyze using moving averages. Is stock above/below 10-week and 40-week MA?]

### 2. Pattern Recognition
[Evaluate the code-detected pattern honestly.
- If a pattern was detected by code: assess its quality and confirm or challenge the detection.
- If NO pattern was detected (best_pattern is None): clearly state "현재 명확한 베이스 패턴이 형성되지 않았습니다" and explain the current chart structure instead (e.g., uptrend, downtrend, consolidation, extended, etc.).
- Do NOT force a pattern label when one doesn't exist. Ambiguous structures are NOT Cup with Handle.]

### 3. Volume Behavior
[Use both the chart and the code-detected volume analysis. Are accumulation/distribution days concerning?]

### 4. CAN SLIM Fundamental Assessment
[Evaluate EACH CAN SLIM factor (C, A, N, S, L, I, M) using the raw data provided and O'Neil's original rules.
For each factor, state whether it PASSES or FAILS O'Neil's criteria and explain why.
Be specific with numbers - quote the actual EPS growth rates, ROE, RS Rating, etc.]

### 5. Buy Point & Entry
[Use the code-detected pivot point as reference. Is the stock at, near, or far from the buy point?
Current price vs. pivot point relationship.]

### 6. Risk Management
[Stop-loss level (7-8% below buy point). Risk/reward ratio.]

### 7. Pattern Quality & Faults
[Address any faults detected by the code. Are they valid concerns?
What is the base stage and what does it mean for risk?]

### 8. FINAL VERDICT
[BUY NOW / WATCH & WAIT / AVOID -- with specific reasoning integrating technical analysis AND each CAN SLIM factor.
Consider Market Direction (M) as O'Neil says it's "50% of the entire investing game."]

---
Be specific with price levels and percentages. Give your honest professional opinion.
Integrate BOTH technical chart analysis and ALL CAN SLIM fundamental factors in your final verdict.
"""

    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[analysis_prompt, image],
        config=types.GenerateContentConfig(
            system_instruction=WILLIAM_ONEIL_ENHANCED_PERSONA,
        )
    )

    print("[OK] V2 Analysis complete!")
    return _remove_emojis(response.text)
