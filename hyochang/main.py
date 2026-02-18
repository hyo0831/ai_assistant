"""
윌리엄 오닐 페르소나 투자 어시스턴트 (William O'Neil AI Investment Assistant)
"""

import os
import yfinance as yf
import mplfinance as mpf
import pandas as pd
from datetime import datetime, timedelta
import google.generativeai as genai
from PIL import Image
import re
import json
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from system_prompt import WILLIAM_ONEIL_ENHANCED_PERSONA
from feedback_manager import FeedbackManager, collect_feedback
from pattern_detector import run_pattern_detection
from version import VERSION, VERSION_NAME

# ====================================================================
# CONFIGURATION
# ====================================================================

# Gemini API Key (환경변수에서 로드)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_API_KEY_HERE":
    raise ValueError(
        "GEMINI_API_KEY is not set. Please set it as an environment variable.\n"
        "Get your API key from: https://aistudio.google.com/app/apikey\n"
        "Set it using: export GEMINI_API_KEY='your-key-here' (Mac/Linux) or "
        "$env:GEMINI_API_KEY='your-key-here' (Windows PowerShell)"
    )

# 차트 저장 경로
CHART_OUTPUT_PATH = "chart.png"

# ====================================================================
# STEP 1: 윌리엄 오닐 스타일 차트 생성기 (The Eye)
# ====================================================================

def fetch_stock_data(ticker: str, period: str = "3y", interval: str = "1wk") -> pd.DataFrame:
    """
    yfinance를 사용하여 주가 데이터 다운로드

    Args:
        ticker: 종목 코드 (예: "AAPL", "TSLA", "005930.KS")
        period: 데이터 기간 (기본: 3년 - 주봉 분석에 적합)
        interval: 데이터 간격 (기본: '1wk' 주봉, '1d' 일봉, '1mo' 월봉)

    Returns:
        OHLCV 데이터프레임
    """
    print(f"[*] Fetching {interval} data for {ticker} (period: {period})...")
    stock = yf.Ticker(ticker)
    df = stock.history(period=period, interval=interval)

    if df.empty:
        raise ValueError(f"No data found for ticker: {ticker}")

    interval_name = {"1wk": "weeks", "1d": "days", "1mo": "months"}.get(interval, "bars")
    print(f"[OK] Downloaded {len(df)} {interval_name} of data")
    return df


def calculate_moving_averages(df: pd.DataFrame, short_window: int = 10, long_window: int = 40) -> pd.DataFrame:
    """
    이동평균선 계산

    주봉 차트: 10주, 40주 이동평균 (William O'Neil의 핵심 지표)
    일봉 차트: 50일, 200일 이동평균

    Args:
        df: OHLCV 데이터프레임
        short_window: 단기 이동평균 기간 (주봉: 10, 일봉: 50)
        long_window: 장기 이동평균 기간 (주봉: 40, 일봉: 200)

    Returns:
        이동평균선이 추가된 데이터프레임
    """
    df[f'MA{short_window}'] = df['Close'].rolling(window=short_window).mean()
    df[f'MA{long_window}'] = df['Close'].rolling(window=long_window).mean()
    # 호환성을 위해 기존 컬럼명도 유지
    df['MA50'] = df[f'MA{short_window}']
    df['MA200'] = df[f'MA{long_window}']
    return df


def create_oneil_chart(ticker: str, df: pd.DataFrame, output_path: str = CHART_OUTPUT_PATH,
                       interval: str = "1wk"):
    """
    윌리엄 오닐 스타일 차트 생성 및 저장

    핵심 스타일 요소:
    1. Linear Scale (선형 스케일) - 가격 직관적 표시
    2. 주봉: 10주/40주 이동평균선 (O'Neil의 핵심 지표)
       일봉: 50일/200일 이동평균선
    3. 거래량 바 (상승=빨강, 하락=파랑)
    4. 깔끔한 Yahoo 스타일

    Args:
        ticker: 종목 코드
        df: OHLCV + MA 데이터프레임
        output_path: 저장 경로
        interval: 차트 간격 ('1wk', '1d', '1mo')
    """
    print(f"[*] Creating William O'Neil style chart...")

    # 주봉인지 일봉인지에 따라 레이블 설정
    if interval == '1wk':
        ma_labels = ('10-Week MA', '40-Week MA')
    else:
        ma_labels = ('50-Day MA', '200-Day MA')

    # 이동평균선 설정
    apds = [
        mpf.make_addplot(df['MA50'], color='blue', width=1.5, label=ma_labels[0]),
        mpf.make_addplot(df['MA200'], color='red', width=1.5, label=ma_labels[1])
    ]

    # 윌리엄 오닐 스타일 설정
    style = mpf.make_mpf_style(
        base_mpf_style='yahoo',
        rc={
            'font.size': 10,
            'axes.labelsize': 12,
            'axes.titlesize': 14,
            'xtick.labelsize': 10,
            'ytick.labelsize': 10,
            'figure.facecolor': 'white',
            'axes.facecolor': 'white'
        }
    )

    # 차트 생성 및 저장
    mpf.plot(
        df,
        type='candle',
        style=style,
        title=f'\n{ticker} - William O\'Neil Style Weekly Chart Analysis',
        ylabel='Price',
        ylabel_lower='Volume',
        volume=True,
        addplot=apds,
        figsize=(16, 10),
        volume_panel=1,
        panel_ratios=(3, 1),
        tight_layout=True,
        savefig=dict(
            fname=output_path,
            dpi=150,
            bbox_inches='tight'
        ),
        returnfig=False
    )

    print(f"[OK] Chart saved to: {output_path}")


# ====================================================================
# STEP 2: 윌리엄 오닐 페르소나 시스템 프롬프트 (The Brain)
# ====================================================================
# 시스템 프롬프트는 system_prompt.py에서 import
# WILLIAM_ONEIL_ENHANCED_PERSONA 사용


# ====================================================================
# STEP 3: AI 분석 실행 함수 (Execution)
# ====================================================================

def analyze_chart_with_gemini(image_path: str, ticker: str, df: pd.DataFrame = None,
                              feedback_manager: FeedbackManager = None) -> str:
    """
    Gemini 1.5 Flash를 사용하여 차트 분석

    Args:
        image_path: 차트 이미지 경로
        ticker: 종목 코드
        df: OHLCV 데이터프레임 (정확한 날짜/가격 정보 제공)
        feedback_manager: 피드백 매니저 (과거 학습 데이터 활용)

    Returns:
        AI 분석 결과 텍스트
    """
    print(f"[*] Analyzing chart with Gemini (William O'Neil persona)...")

    # Gemini API 설정
    genai.configure(api_key=GEMINI_API_KEY)

    # 모델 초기화 (system_instruction으로 향상된 페르소나 주입)
    model = genai.GenerativeModel(
        model_name='gemini-2.5-flash',
        system_instruction=WILLIAM_ONEIL_ENHANCED_PERSONA
    )

    # 이미지 로드
    image = Image.open(image_path)

    # 데이터 요약 정보 생성 (정확한 날짜/가격 제공)
    data_summary = ""
    if df is not None and not df.empty:
        recent_data = df.tail(52)  # 최근 1년 (52주) 데이터

        # 최고가/최저가 정보
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

    # 과거 피드백 컨텍스트 추가 (학습)
    feedback_context = ""
    if feedback_manager:
        feedback_context = feedback_manager.get_feedback_context(ticker)

    # 분석 요청 프롬프트
    analysis_prompt = f"""
Analyze this WEEKLY stock chart for {ticker}.
{data_summary}
{feedback_context}

IMPORTANT: This is a WEEKLY chart, not a daily chart. Each candle represents one week of trading.
When analyzing patterns, use weekly timeframes (e.g., "Cup with Handle" should be 7-65 weeks, not days).

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

    # Gemini에 분석 요청
    response = model.generate_content([analysis_prompt, image])

    print("[OK] Analysis complete!")

    # Windows 콘솔 호환성을 위해 이모지 제거
    clean_text = re.sub(r'[^\x00-\x7F\n\r\t가-힣]', '', response.text)

    return clean_text


def parse_pattern_data(analysis_text: str) -> dict:
    """
    AI 분석 결과에서 JSON 패턴 데이터 추출

    Args:
        analysis_text: AI 분석 텍스트

    Returns:
        패턴 데이터 딕셔너리 (추출 실패 시 None)
    """
    try:
        # JSON 블록 찾기 (```json ... ``` 또는 { ... })
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


def create_annotated_chart(ticker: str, df: pd.DataFrame, pattern_data: dict,
                          output_path: str = "chart_annotated.png", interval: str = "1wk"):
    """
    패턴 표시가 포함된 차트 생성

    Args:
        ticker: 종목 코드
        df: OHLCV + MA 데이터프레임
        pattern_data: 패턴 정보 딕셔너리
        output_path: 저장 경로
        interval: 차트 간격
    """
    print(f"[*] Creating annotated chart with pattern overlay...")

    if not pattern_data or 'key_levels' not in pattern_data:
        print("[WARNING] No pattern data available, creating standard chart")
        create_oneil_chart(ticker, df, output_path, interval)
        return

    # 주봉인지 일봉인지에 따라 레이블 설정
    if interval == '1wk':
        ma_labels = ('10-Week MA', '40-Week MA')
    else:
        ma_labels = ('50-Day MA', '200-Day MA')

    # 이동평균선 설정
    apds = [
        mpf.make_addplot(df['MA50'], color='blue', width=1.5, label=ma_labels[0]),
        mpf.make_addplot(df['MA200'], color='red', width=1.5, label=ma_labels[1])
    ]

    # 윌리엄 오닐 스타일 설정
    style = mpf.make_mpf_style(
        base_mpf_style='yahoo',
        rc={
            'font.size': 10,
            'axes.labelsize': 12,
            'axes.titlesize': 14,
            'xtick.labelsize': 10,
            'ytick.labelsize': 10,
            'figure.facecolor': 'white',
            'axes.facecolor': 'white'
        }
    )

    # 패턴 정보 추출
    key_levels = pattern_data.get('key_levels', {})
    buy_point = key_levels.get('buy_point')
    stop_loss = key_levels.get('stop_loss')
    support = key_levels.get('support')
    resistance = key_levels.get('resistance')
    pattern_type = pattern_data.get('pattern_type', 'Unknown')
    verdict = pattern_data.get('verdict', 'N/A')

    # 수평선 데이터 준비
    hlines_data = []  # (label, price, color, linestyle, linewidth)

    if buy_point:
        hlines_data.append(('Buy Point', buy_point, 'green', '--', 2))

    if stop_loss:
        hlines_data.append(('Stop Loss', stop_loss, 'red', '--', 2))

    if support and support != stop_loss:
        hlines_data.append(('Support', support, 'orange', ':', 1.5))

    if resistance and resistance != buy_point:
        hlines_data.append(('Resistance', resistance, 'purple', ':', 1.5))

    # 차트 제목에 패턴 정보 포함
    title_text = f'\n{ticker} - William O\'Neil Weekly Chart\n'
    title_text += f'Pattern: {pattern_type} | Verdict: {verdict}'

    # 차트 생성
    fig, axes = mpf.plot(
        df,
        type='candle',
        style=style,
        title=title_text,
        ylabel='Price',
        ylabel_lower='Volume',
        volume=True,
        addplot=apds,
        figsize=(16, 10),
        volume_panel=1,
        panel_ratios=(3, 1),
        tight_layout=True,
        returnfig=True
    )

    # 수평선과 레이블 추가
    ax = axes[0]  # 메인 차트 축
    x_min, x_max = ax.get_xlim()
    label_x = x_min + (x_max - x_min) * 0.02  # 왼쪽에서 2% 위치

    for label, price, color, linestyle, linewidth in hlines_data:
        # 수평선 그리기
        ax.axhline(y=price, color=color, linestyle=linestyle, linewidth=linewidth, alpha=0.7)

        # 레이블 추가
        ax.text(label_x, price, f' {label}: ${price:.2f}',
                fontsize=9, color=color, fontweight='bold',
                verticalalignment='center',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='white', edgecolor=color, alpha=0.9))

    # 패턴 라인 그리기 (실제 패턴 형태 시각화)
    pattern_points = pattern_data.get('pattern_points', {})
    if pattern_points:
        left_peak_idx = pattern_points.get('left_peak_week')
        bottom_idx = pattern_points.get('bottom_week')
        right_peak_idx = pattern_points.get('right_peak_week')
        handle_end_idx = pattern_points.get('handle_end_week')

        # 실제 가격 데이터에서 좌표 추출
        points_to_plot = []  # (index, price, label, step_num)

        if pattern_type == "Cup with Handle":
            # ① 왼쪽 정점 (Left Lip)
            if left_peak_idx is not None and 0 <= left_peak_idx < len(df):
                left_price = df.iloc[left_peak_idx]['High']
                points_to_plot.append((left_peak_idx, left_price, '단계', 1))

            # ② 컵 바닥 (Cup Bottom)
            if bottom_idx is not None and 0 <= bottom_idx < len(df):
                bottom_price = df.iloc[bottom_idx]['Low']
                points_to_plot.append((bottom_idx, bottom_price, '단계', 2))

            # ③ 오른쪽 정점 (Right Lip)
            if right_peak_idx is not None and 0 <= right_peak_idx < len(df):
                right_price = df.iloc[right_peak_idx]['High']
                points_to_plot.append((right_peak_idx, right_price, '단계', 3))

            # ④ 현재/핸들 끝 (Current/Handle End)
            if handle_end_idx is not None and 0 <= handle_end_idx < len(df):
                handle_price = df.iloc[handle_end_idx]['Close']
                points_to_plot.append((handle_end_idx, handle_price, '단계', 4))

            # ⑤ 매수 포인트 표시
            if buy_point and right_peak_idx is not None:
                points_to_plot.append((right_peak_idx, buy_point, '매수', 5))

            # 패턴 곡선 그리기
            if len(points_to_plot) >= 3:
                # 주요 포인트들을 연결하는 선
                x_coords = [p[0] for p in points_to_plot[:4]]  # ①②③④만
                y_coords = [p[1] for p in points_to_plot[:4]]

                # 패턴 라인 그리기 (굵은 빨간 선)
                ax.plot(x_coords, y_coords, 'r-', linewidth=3, alpha=0.7,
                       label='Pattern Outline', zorder=10)

                # 각 포인트에 원형 마커와 번호 표시
                for idx, price, label_type, step_num in points_to_plot:
                    if step_num <= 4:  # ①②③④
                        # 큰 원형 마커
                        ax.plot(idx, price, 'o', markersize=15, color='red',
                               markeredgecolor='white', markeredgewidth=2, zorder=15)

                        # 단계 번호 (①②③④)
                        circle_numbers = ['①', '②', '③', '④', '⑤']
                        ax.text(idx, price, circle_numbers[step_num-1],
                               fontsize=12, fontweight='bold', color='white',
                               ha='center', va='center', zorder=20)

                        # 단계 레이블 (하단)
                        if step_num == 1:
                            stage_label = '①단계\n(시작)'
                        elif step_num == 2:
                            stage_label = '②단계\n(저점)'
                        elif step_num == 3:
                            stage_label = '③단계\n(반등)'
                        elif step_num == 4:
                            stage_label = '④단계\n(재상승)'

                        y_offset = (ax.get_ylim()[1] - ax.get_ylim()[0]) * 0.05
                        ax.text(idx, price - y_offset, stage_label,
                               fontsize=9, ha='center', va='top',
                               bbox=dict(boxstyle='round,pad=0.5',
                                       facecolor='yellow', edgecolor='red', alpha=0.8))

                    elif step_num == 5:  # ⑤ 매수 포인트
                        ax.plot(idx, price, '^', markersize=20, color='green',
                               markeredgecolor='white', markeredgewidth=2, zorder=15)
                        ax.text(idx, price, '⑤\n매수', fontsize=10, fontweight='bold',
                               color='green', ha='center', va='bottom',
                               bbox=dict(boxstyle='round,pad=0.3',
                                       facecolor='white', edgecolor='green', alpha=0.9))

        elif pattern_type == "Double Bottom":
            # ① 첫 번째 바닥
            if left_peak_idx is not None and 0 <= left_peak_idx < len(df):
                first_bottom = df.iloc[left_peak_idx]['Low']
                points_to_plot.append((left_peak_idx, first_bottom, '단계', 1))

            # ② 중간 피크
            if bottom_idx is not None and 0 <= bottom_idx < len(df):
                middle_peak = df.iloc[bottom_idx]['High']
                points_to_plot.append((bottom_idx, middle_peak, '단계', 2))

            # ③ 두 번째 바닥
            if right_peak_idx is not None and 0 <= right_peak_idx < len(df):
                second_bottom = df.iloc[right_peak_idx]['Low']
                points_to_plot.append((right_peak_idx, second_bottom, '단계', 3))

            # ④ 현재 위치
            if handle_end_idx is not None and 0 <= handle_end_idx < len(df):
                current_price = df.iloc[handle_end_idx]['Close']
                points_to_plot.append((handle_end_idx, current_price, '단계', 4))

            # W 패턴 라인 그리기
            if len(points_to_plot) >= 3:
                x_coords = [p[0] for p in points_to_plot[:4]]
                y_coords = [p[1] for p in points_to_plot[:4]]

                ax.plot(x_coords, y_coords, 'b-', linewidth=3, alpha=0.7,
                       label='Double Bottom Pattern', zorder=10)

                # 마커와 레이블
                labels = ['①단계\n(1차저점)', '②단계\n(반등)', '③단계\n(2차저점)', '④단계\n(재상승)']
                for i, (idx, price, _, step_num) in enumerate(points_to_plot[:4]):
                    ax.plot(idx, price, 'o', markersize=15, color='blue',
                           markeredgecolor='white', markeredgewidth=2, zorder=15)

                    circle_numbers = ['①', '②', '③', '④']
                    ax.text(idx, price, circle_numbers[i],
                           fontsize=12, fontweight='bold', color='white',
                           ha='center', va='center', zorder=20)

                    y_offset = (ax.get_ylim()[1] - ax.get_ylim()[0]) * 0.05
                    ax.text(idx, price - y_offset, labels[i],
                           fontsize=9, ha='center', va='top',
                           bbox=dict(boxstyle='round,pad=0.5',
                                   facecolor='lightyellow', edgecolor='blue', alpha=0.8))

    # 범례 추가
    handles, labels = ax.get_legend_handles_labels()
    if handles:
        ax.legend(loc='upper left', fontsize=9, framealpha=0.9)

    # 저장
    fig.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close(fig)

    print(f"[OK] Annotated chart saved to: {output_path}")


# ====================================================================
# MAIN EXECUTION — V1 (기본: AI 이미지 분석만)
# ====================================================================

def main_v1(ticker: str):
    """
    V1 메인 실행 함수 (기존 버전)
    AI가 차트 이미지를 직접 보고 분석

    Args:
        ticker: 분석할 종목 코드
    """
    print("=" * 80)
    print("WILLIAM O'NEIL AI INVESTMENT ASSISTANT [V1 - Basic]")
    print("=" * 80)
    print(f"Target: {ticker}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print()

    try:
        # Step 1: 데이터 다운로드 (주봉, 3년치)
        interval = "1wk"
        df = fetch_stock_data(ticker, period="3y", interval=interval)

        # Step 2: 이동평균선 계산 (주봉: 10주, 40주)
        df = calculate_moving_averages(df, short_window=10, long_window=40)

        # Step 3: 기본 차트 생성 (AI 분석용)
        create_oneil_chart(ticker, df, interval=interval)

        # Step 4: AI 분석 (데이터프레임 + 피드백 매니저 전달)
        feedback_manager = FeedbackManager()
        analysis = analyze_chart_with_gemini(CHART_OUTPUT_PATH, ticker, df, feedback_manager)

        # 결과 출력
        _print_analysis_result(analysis)

        # 피드백 수집
        _collect_and_save_feedback(ticker, analysis, feedback_manager)

    except Exception as e:
        print(f"[ERROR] {e}")
        raise


# ====================================================================
# MAIN EXECUTION — V2 (향상: 코드 패턴 감지 + AI 해석)
# ====================================================================

def analyze_chart_v2(image_path: str, ticker: str, df: pd.DataFrame,
                     pattern_result: dict,
                     feedback_manager: FeedbackManager = None) -> str:
    """
    V2: 코드 기반 패턴 감지 결과를 AI에게 전달하여 해석

    Args:
        image_path: 차트 이미지 경로
        ticker: 종목 코드
        df: OHLCV 데이터프레임
        pattern_result: pattern_detector.run_pattern_detection() 결과
        feedback_manager: 피드백 매니저

    Returns:
        AI 분석 결과 텍스트
    """
    print(f"[*] V2: Analyzing with code-detected patterns + AI interpretation...")

    genai.configure(api_key=GEMINI_API_KEY)

    model = genai.GenerativeModel(
        model_name='gemini-2.5-flash',
        system_instruction=WILLIAM_ONEIL_ENHANCED_PERSONA
    )

    image = Image.open(image_path)

    # 데이터 요약 정보
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

    # 코드 기반 패턴 감지 결과
    pattern_summary = pattern_result.get('summary', 'No pattern detection results available.')

    # 피드백 컨텍스트
    feedback_context = ""
    if feedback_manager:
        feedback_context = feedback_manager.get_feedback_context(ticker)

    # V2 분석 프롬프트 (코드 감지 결과를 참고하도록)
    analysis_prompt = f"""
Analyze this WEEKLY stock chart for {ticker}.

{data_summary}

## CODE-BASED PATTERN DETECTION RESULTS
The following patterns and metrics were detected by our automated pattern detection engine.
Use these results as quantitative reference data to support your visual analysis of the chart.
If the code detection and your visual analysis conflict, explain the discrepancy.

{pattern_summary}

{feedback_context}

IMPORTANT: This is a WEEKLY chart. Each candle = one week of trading.

Based on BOTH the chart image AND the code-detected pattern data above, provide your analysis:

## CHART ANALYSIS: {ticker}

### 1. Trend Status
[Analyze using moving averages. Is stock above/below 10-week and 40-week MA?]

### 2. Pattern Recognition
[Evaluate the code-detected pattern. Do you agree with the detection? Is the pattern valid per O'Neil's criteria?
If code detected a pattern, assess its quality. If no pattern was detected, explain what you see.]

### 3. Volume Behavior
[Use both the chart and the code-detected volume analysis. Are accumulation/distribution days concerning?]

### 4. Buy Point & Entry
[Use the code-detected pivot point as reference. Is the stock at, near, or far from the buy point?
Current price vs. pivot point relationship.]

### 5. Risk Management
[Stop-loss level (7-8% below buy point). Risk/reward ratio.]

### 6. Pattern Quality & Faults
[Address any faults detected by the code. Are they valid concerns?
What is the base stage and what does it mean for risk?]

### 7. FINAL VERDICT
[BUY NOW / WATCH & WAIT / AVOID — with specific reasoning integrating both code data and chart analysis]

---
Be specific with price levels and percentages. Give your honest professional opinion.
"""

    response = model.generate_content([analysis_prompt, image])

    print("[OK] V2 Analysis complete!")

    clean_text = re.sub(r'[^\x00-\x7F\n\r\t가-힣]', '', response.text)
    return clean_text


def main_v2(ticker: str):
    """
    V2 메인 실행 함수 (향상 버전)
    코드 기반 패턴 감지 → AI가 결과를 해석

    Args:
        ticker: 분석할 종목 코드
    """
    print("=" * 80)
    print("WILLIAM O'NEIL AI INVESTMENT ASSISTANT [V2 - Enhanced Pattern Detection]")
    print("=" * 80)
    print(f"Target: {ticker}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print()

    try:
        # Step 1: 데이터 다운로드 (주봉, 3년치)
        interval = "1wk"
        df = fetch_stock_data(ticker, period="3y", interval=interval)

        # Step 2: 이동평균선 계산 (주봉: 10주, 40주)
        df = calculate_moving_averages(df, short_window=10, long_window=40)

        # Step 3: 코드 기반 패턴 감지 실행
        print()
        pattern_result = run_pattern_detection(df, ticker)
        print()

        # 코드 감지 결과 미리보기 출력
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

        # Step 4: 차트 생성
        create_oneil_chart(ticker, df, interval=interval)

        # Step 5: V2 AI 분석 (코드 감지 결과 + 차트 이미지)
        feedback_manager = FeedbackManager()
        analysis = analyze_chart_v2(
            CHART_OUTPUT_PATH, ticker, df, pattern_result, feedback_manager
        )

        # 결과 출력
        _print_analysis_result(analysis)

        # 피드백 수집
        _collect_and_save_feedback(ticker, analysis, feedback_manager)

    except Exception as e:
        print(f"[ERROR] {e}")
        raise


# ====================================================================
# 공통 유틸리티 함수
# ====================================================================

def _print_analysis_result(analysis: str):
    """분석 결과 출력"""
    print()
    print("=" * 80)
    print("ANALYSIS RESULT")
    print("=" * 80)
    print()
    print(analysis)
    print()
    print("=" * 80)
    print(f"Chart saved: {CHART_OUTPUT_PATH}")
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


# ====================================================================
# ENTRY POINT — 모드 선택
# ====================================================================

if __name__ == "__main__":
    print()
    print("=" * 80)
    print(f"  WILLIAM O'NEIL AI INVESTMENT ASSISTANT  v{VERSION}")
    print("=" * 80)
    print()
    print("  [1] V1 - Basic (AI image analysis only)")
    print("      AI가 차트 이미지를 직접 보고 분석합니다.")
    print()
    print("  [2] V2 - Enhanced (Code pattern detection + AI interpretation)")
    print("      코드가 패턴을 먼저 감지한 후, AI가 결과를 해석합니다.")
    print("      더 정확한 수치 기반 분석을 제공합니다.")
    print()
    print("=" * 80)

    mode = input("  Select mode (1 or 2): ").strip()
    if mode not in ('1', '2'):
        print("  Invalid selection. Defaulting to V2.")
        mode = '2'

    ticker = input("  Enter ticker symbol (e.g., AAPL): ").strip().upper()
    if not ticker:
        ticker = "AAPL"
        print(f"  No ticker entered. Using default: {ticker}")

    print()

    if mode == '1':
        main_v1(ticker)
    else:
        main_v2(ticker)
