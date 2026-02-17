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
            "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n"
            "CRITICAL LANGUAGE REQUIREMENT — 반드시 지켜야 함:\n"
            "모든 분석 텍스트를 한국어(Korean)로 작성하라.\n"
            "영어로 답변하면 안 된다. 반드시 한국어로만 답변하라.\n"
            "단, 아래 기술 용어는 영어 그대로 사용 가능:\n"
            "Cup with Handle, Double Bottom, Flat Base, High Tight Flag,\n"
            "CAN SLIM, RS Rating, EPS, ROE, P/E, Buy Point, Stop Loss,\n"
            "Accumulation, Distribution, Breakout, Pivot Point, Base Stage\n"
            "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n"
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
{lang_instruction}

{ticker} 종목의 {chart_type_text} 주식 차트를 분석하라.
IMPORTANT: {timeframe_note}
{data_summary}
{feedback_context}

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
{lang_instruction}

{ticker} 종목의 {chart_type_text} 주식 차트를 분석하라.
IMPORTANT: {timeframe_note}

{data_summary}

---
## [보조 데이터 1] 정량적 지표 (코드 계산값 — 참고용)
아래 수치는 알고리즘이 계산한 정량 데이터다.
RS Rating, 거래량 추세, Base Stage 등 수치 정보를 활용하라.
단, 패턴 이름(Cup-with-Handle 등)은 참고만 하고, 실제 패턴 판단은 반드시 차트 이미지를 직접 보고 결정하라.

{pattern_summary}

---
## [보조 데이터 2] CAN SLIM 펀더멘털 데이터
각 CAN SLIM 항목(C, A, N, S, L, I, M)별 실제 데이터다.
오닐의 원칙에 따라 각 항목을 직접 평가하라. 사전 점수는 무시하라.

{fundamental_summary if fundamental_summary else "펀더멘털 데이터 없음."}

{feedback_context}

---
## 분석 형식 (아래 섹션 순서대로 한국어로 작성)

## 차트 분석: {ticker}

### 1. 추세 현황
이동평균선(10주선/40주선 또는 50일선/200일선)을 기준으로 현재 추세를 분석하라.
주가가 이동평균선 위/아래 어디에 있는지, 이동평균선 방향은 어떤지 설명하라.

### 2. 패턴 인식
차트 이미지를 직접 보고 패턴을 판단하라.
- 명확한 패턴이 보이면: 패턴명, 형성 기간, 깊이, 품질을 설명하라.
- 명확한 패턴이 없으면: "현재 명확한 베이스 패턴이 형성되지 않았습니다"라고 명시하고 현재 차트 구조(상승추세, 하락추세, 횡보, 과매수 구간 등)를 설명하라.
- 코드가 패턴을 감지했더라도 차트에서 확인이 안 되면 "코드 감지 결과와 달리 시각적으로 확인되지 않습니다"라고 밝혀라.
- 억지로 패턴을 붙이지 마라.

### 3. 거래량 분석
차트의 거래량 바와 정량 데이터를 함께 활용하라.
매집/분산 신호, 돌파 시 거래량 급증 여부를 분석하라.

### 4. CAN SLIM 펀더멘털 평가
C, A, N, S, L, I, M 각 항목별로 오닐 기준 PASS/FAIL 여부와 근거를 명시하라.
실제 수치(EPS 성장률, ROE, RS Rating 등)를 인용하라.

### 5. 매수 포인트 & 진입 전략
Pivot Point 기준 현재 주가 위치를 설명하라.
매수 가능 구간인지, 추가 조정이 필요한지 판단하라.

### 6. 리스크 관리
손절 기준(매수 포인트 7~8% 아래)과 리스크/수익 비율을 제시하라.

### 7. 패턴 결함 & 주의사항
코드가 감지한 결함이 실제로 유효한지 평가하라.
Base Stage와 그것이 위험도에 미치는 영향을 설명하라.

### 8. 최종 판단
BUY NOW / WATCH & WAIT / AVOID 중 하나를 명확히 제시하라.
기술적 분석과 CAN SLIM 펀더멘털을 통합한 근거를 제시하라.
시장 방향(M)은 오닐이 "투자의 50%"라고 강조했음을 고려하라.

---
구체적인 가격 레벨과 퍼센트를 사용하라. 솔직하고 전문적인 의견을 제시하라.
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
