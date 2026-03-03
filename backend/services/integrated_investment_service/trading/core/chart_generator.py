import mplfinance as mpf
import matplotlib.pyplot as plt
import pandas as pd

from core.config import CHART_OUTPUT_PATH


def create_oneil_chart(ticker: str, df: pd.DataFrame, output_path: str = CHART_OUTPUT_PATH,
                       interval: str = "1wk", pivot_info: dict = None):
    """
    윌리엄 오닐 스타일 차트 생성 및 저장

    Args:
        ticker: 종목 코드
        df: OHLCV + MA 데이터프레임
        output_path: 저장 경로
        interval: 차트 간격 ('1wk', '1d', '1mo')
        pivot_info: 피봇 포인트 정보 dict
            {'price': float, 'date': 'YYYY-MM-DD', 'pattern_type': str}
    """
    print(f"[*] Creating William O'Neil style chart...")

    if interval == '1wk':
        ma_labels = ('10-Week MA', '40-Week MA')
    else:
        ma_labels = ('50-Day MA', '200-Day MA')

    apds = [
        mpf.make_addplot(df['MA50'], color='blue', width=1.5, label=ma_labels[0]),
        mpf.make_addplot(df['MA200'], color='red', width=1.5, label=ma_labels[1])
    ]

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

    need_pivot = pivot_info and pivot_info.get('price') and pivot_info.get('date')

    fig, axes = mpf.plot(
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
        returnfig=True,
    )

    if need_pivot:
        _draw_pivot_arrow(fig, axes[0], df, pivot_info)

    fig.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close(fig)

    print(f"[OK] Chart saved to: {output_path}")


def _draw_pivot_arrow(fig, ax, df: pd.DataFrame, pivot_info: dict):
    """
    피봇 포인트 위치에 아래↓ 방향 화살표와 레이블 표시

    Args:
        fig: matplotlib Figure
        ax: 가격 차트 Axes
        df: OHLCV 데이터프레임
        pivot_info: {'price': float, 'date': 'YYYY-MM-DD', 'pattern_type': str}
    """
    pivot_price = pivot_info['price']
    pivot_date_str = pivot_info['date']
    pattern_type = pivot_info.get('pattern_type', 'Pivot')

    try:
        pivot_date = pd.to_datetime(pivot_date_str)
        if df.index.tz is not None and pivot_date.tzinfo is None:
            pivot_date = pivot_date.tz_localize(df.index.tz)
        elif df.index.tz is None and pivot_date.tzinfo is not None:
            pivot_date = pivot_date.tz_localize(None)
        date_diffs = abs(df.index - pivot_date)
        x_idx = date_diffs.argmin()
    except Exception as e:
        print(f"[WARNING] Pivot arrow skipped: {e}")
        return

    candle_high = df.iloc[x_idx]['High']
    offset = candle_high * 0.04

    arrow_y_start = candle_high + offset * 2.5
    arrow_y_end = candle_high + offset * 0.3

    y_min, y_max = ax.get_ylim()
    if arrow_y_start > y_max:
        ax.set_ylim(y_min, arrow_y_start * 1.05)

    ax.annotate(
        f'Pivot\n${pivot_price:.2f}',
        xy=(x_idx, arrow_y_end),
        xytext=(x_idx, arrow_y_start),
        fontsize=9,
        fontweight='bold',
        color='white',
        ha='center',
        va='bottom',
        bbox=dict(
            boxstyle='round,pad=0.3',
            facecolor='#E8541A',
            edgecolor='#E8541A',
            alpha=0.9
        ),
        arrowprops=dict(
            arrowstyle='-|>',
            color='#E8541A',
            lw=2,
            mutation_scale=18,
        )
    )

    print(f"[OK] Pivot arrow drawn at {pivot_date_str} (${pivot_price:.2f}, x={x_idx})")


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

    if interval == '1wk':
        ma_labels = ('10-Week MA', '40-Week MA')
    else:
        ma_labels = ('50-Day MA', '200-Day MA')

    apds = [
        mpf.make_addplot(df['MA50'], color='blue', width=1.5, label=ma_labels[0]),
        mpf.make_addplot(df['MA200'], color='red', width=1.5, label=ma_labels[1])
    ]

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

    key_levels = pattern_data.get('key_levels', {})
    buy_point = key_levels.get('buy_point')
    stop_loss = key_levels.get('stop_loss')
    support = key_levels.get('support')
    resistance = key_levels.get('resistance')
    pattern_type = pattern_data.get('pattern_type', 'Unknown')
    verdict = pattern_data.get('verdict', 'N/A')

    hlines_data = []

    if buy_point:
        hlines_data.append(('Buy Point', buy_point, 'green', '--', 2))
    if stop_loss:
        hlines_data.append(('Stop Loss', stop_loss, 'red', '--', 2))
    if support and support != stop_loss:
        hlines_data.append(('Support', support, 'orange', ':', 1.5))
    if resistance and resistance != buy_point:
        hlines_data.append(('Resistance', resistance, 'purple', ':', 1.5))

    title_text = f'\n{ticker} - William O\'Neil Weekly Chart\n'
    title_text += f'Pattern: {pattern_type} | Verdict: {verdict}'

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

    ax = axes[0]
    x_min, x_max = ax.get_xlim()
    label_x = x_min + (x_max - x_min) * 0.02

    for label, price, color, linestyle, linewidth in hlines_data:
        ax.axhline(y=price, color=color, linestyle=linestyle, linewidth=linewidth, alpha=0.7)
        ax.text(label_x, price, f' {label}: ${price:.2f}',
                fontsize=9, color=color, fontweight='bold',
                verticalalignment='center',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='white', edgecolor=color, alpha=0.9))

    pattern_points = pattern_data.get('pattern_points', {})
    if pattern_points:
        left_peak_idx = pattern_points.get('left_peak_week')
        bottom_idx = pattern_points.get('bottom_week')
        right_peak_idx = pattern_points.get('right_peak_week')
        handle_end_idx = pattern_points.get('handle_end_week')

        points_to_plot = []

        if pattern_type == "Cup with Handle":
            if left_peak_idx is not None and 0 <= left_peak_idx < len(df):
                left_price = df.iloc[left_peak_idx]['High']
                points_to_plot.append((left_peak_idx, left_price, '단계', 1))

            if bottom_idx is not None and 0 <= bottom_idx < len(df):
                bottom_price = df.iloc[bottom_idx]['Low']
                points_to_plot.append((bottom_idx, bottom_price, '단계', 2))

            if right_peak_idx is not None and 0 <= right_peak_idx < len(df):
                right_price = df.iloc[right_peak_idx]['High']
                points_to_plot.append((right_peak_idx, right_price, '단계', 3))

            if handle_end_idx is not None and 0 <= handle_end_idx < len(df):
                handle_price = df.iloc[handle_end_idx]['Close']
                points_to_plot.append((handle_end_idx, handle_price, '단계', 4))

            if buy_point and right_peak_idx is not None:
                points_to_plot.append((right_peak_idx, buy_point, '매수', 5))

            if len(points_to_plot) >= 3:
                x_coords = [p[0] for p in points_to_plot[:4]]
                y_coords = [p[1] for p in points_to_plot[:4]]

                ax.plot(x_coords, y_coords, 'r-', linewidth=3, alpha=0.7,
                        label='Pattern Outline', zorder=10)

                for idx, price, label_type, step_num in points_to_plot:
                    if step_num <= 4:
                        ax.plot(idx, price, 'o', markersize=15, color='red',
                                markeredgecolor='white', markeredgewidth=2, zorder=15)

                        circle_numbers = ['①', '②', '③', '④', '⑤']
                        ax.text(idx, price, circle_numbers[step_num-1],
                                fontsize=12, fontweight='bold', color='white',
                                ha='center', va='center', zorder=20)

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

                    elif step_num == 5:
                        ax.plot(idx, price, '^', markersize=20, color='green',
                                markeredgecolor='white', markeredgewidth=2, zorder=15)
                        ax.text(idx, price, '⑤\n매수', fontsize=10, fontweight='bold',
                                color='green', ha='center', va='bottom',
                                bbox=dict(boxstyle='round,pad=0.3',
                                          facecolor='white', edgecolor='green', alpha=0.9))

        elif pattern_type == "Double Bottom":
            if left_peak_idx is not None and 0 <= left_peak_idx < len(df):
                first_bottom = df.iloc[left_peak_idx]['Low']
                points_to_plot.append((left_peak_idx, first_bottom, '단계', 1))

            if bottom_idx is not None and 0 <= bottom_idx < len(df):
                middle_peak = df.iloc[bottom_idx]['High']
                points_to_plot.append((bottom_idx, middle_peak, '단계', 2))

            if right_peak_idx is not None and 0 <= right_peak_idx < len(df):
                second_bottom = df.iloc[right_peak_idx]['Low']
                points_to_plot.append((right_peak_idx, second_bottom, '단계', 3))

            if handle_end_idx is not None and 0 <= handle_end_idx < len(df):
                current_price = df.iloc[handle_end_idx]['Close']
                points_to_plot.append((handle_end_idx, current_price, '단계', 4))

            if len(points_to_plot) >= 3:
                x_coords = [p[0] for p in points_to_plot[:4]]
                y_coords = [p[1] for p in points_to_plot[:4]]

                ax.plot(x_coords, y_coords, 'b-', linewidth=3, alpha=0.7,
                        label='Double Bottom Pattern', zorder=10)

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

    handles, labels = ax.get_legend_handles_labels()
    if handles:
        ax.legend(loc='upper left', fontsize=9, framealpha=0.9)

    fig.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close(fig)

    print(f"[OK] Annotated chart saved to: {output_path}")
