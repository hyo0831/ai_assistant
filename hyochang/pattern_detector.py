"""
O'Neil Style Chart Pattern Detection Engine (코드 기반 패턴 감지)

chart_analysis_technical_spec.md 기반으로 구현
패턴 감지 → 품질 점수 → 불량 패턴 필터링 → 결과 반환
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Optional


# ====================================================================
# 1. Cup-with-Handle 패턴 감지
# ====================================================================

def detect_cup_with_handle(df: pd.DataFrame, min_weeks: int = 7, max_weeks: int = 65) -> List[Dict]:
    """
    Cup-with-Handle 패턴 감지

    오닐의 정의 기준:
    - 기간: 7주 ~ 65주 (대부분 3~6개월)
    - 깊이: 12% ~ 33% (강세장), 최대 50% (약세장)
    - 바닥: "U" 모양 (V 모양은 위험)
    - 핸들: 상단 1/2에 형성, 하락 8~12% 이내, 하향 드리프트
    - 돌파 거래량: 평균 대비 50%+ 증가

    Args:
        df: 주봉 OHLCV 데이터프레임
        min_weeks: 최소 기간 (주)
        max_weeks: 최대 기간 (주)

    Returns:
        감지된 패턴 리스트
    """
    patterns = []

    if len(df) < min_weeks + 2:
        return patterns

    closes = df['Close'].values
    highs = df['High'].values
    lows = df['Low'].values
    volumes = df['Volume'].values
    dates = df.index

    # 슬라이딩 윈도우로 패턴 탐색 (최근부터 역순으로)
    best_pattern = None
    best_quality = 0

    for duration in range(min_weeks, min(max_weeks + 1, len(df) - 2)):
        start_idx = len(df) - duration - 5  # 핸들 공간 확보
        if start_idx < 0:
            start_idx = 0

        for i in range(max(0, len(df) - max_weeks - 10), len(df) - min_weeks):
            end_idx = min(i + duration, len(df) - 1)
            if end_idx - i < min_weeks:
                continue

            window_highs = highs[i:end_idx + 1]
            window_lows = lows[i:end_idx + 1]
            window_closes = closes[i:end_idx + 1]
            window_volumes = volumes[i:end_idx + 1]

            # 1. 왼쪽 고점 찾기 (처음 1/3 구간에서)
            left_section_end = max(3, len(window_highs) // 3)
            left_peak_rel = np.argmax(window_highs[:left_section_end])
            left_peak = window_highs[left_peak_rel]

            # 2. 바닥 찾기 (중간 구간에서)
            mid_start = left_peak_rel + 1
            mid_end = max(mid_start + 2, len(window_lows) * 2 // 3)
            if mid_start >= len(window_lows) or mid_end > len(window_lows):
                continue

            cup_low_rel = mid_start + np.argmin(window_lows[mid_start:mid_end])
            cup_low = window_lows[cup_low_rel]

            # 3. 깊이 계산
            depth_pct = ((left_peak - cup_low) / left_peak) * 100
            if depth_pct < 12 or depth_pct > 50:
                continue

            # 4. U자형 검증 (V자형 배제)
            bottom_zone = cup_low * 1.03
            weeks_near_bottom = np.sum(window_lows[mid_start:mid_end] <= bottom_zone)
            if weeks_near_bottom < 2:
                continue

            # 5. 오른쪽 고점 찾기 (핸들 시작점)
            right_start = cup_low_rel + 1
            if right_start >= len(window_highs) - 1:
                continue

            right_peak_rel = right_start + np.argmax(window_highs[right_start:])
            right_peak = window_highs[right_peak_rel]

            # 오른쪽 고점이 왼쪽 고점의 80% 이상이어야 함
            if right_peak < left_peak * 0.80:
                continue

            # 6. 핸들 감지 (오른쪽 고점 이후)
            handle_start = i + right_peak_rel
            if handle_start >= len(df) - 1:
                continue

            handle_end = min(handle_start + 10, len(df))
            if handle_end - handle_start < 1:
                continue

            handle_lows = lows[handle_start:handle_end]
            handle_highs = highs[handle_start:handle_end]
            handle_low = np.min(handle_lows)
            handle_depth = ((right_peak - handle_low) / right_peak) * 100

            # 핸들 깊이: 15% 이내
            if handle_depth > 15:
                continue

            # 핸들이 전체 base 상단 1/2에 있는지 확인
            base_midpoint = cup_low + (left_peak - cup_low) / 2
            handle_in_upper_half = handle_low >= base_midpoint

            # 7. 핸들 거래량 감소 확인
            handle_volumes = volumes[handle_start:handle_end]
            base_avg_vol = np.mean(window_volumes)
            handle_avg_vol = np.mean(handle_volumes) if len(handle_volumes) > 0 else base_avg_vol
            vol_dryup = handle_avg_vol < base_avg_vol * 0.8

            # 8. 피벗 포인트 계산
            pivot_point = right_peak

            # 품질 점수 계산
            quality = _calculate_cup_quality(
                depth_pct, handle_depth, vol_dryup,
                weeks_near_bottom, duration, handle_in_upper_half
            )

            if quality > best_quality:
                best_quality = quality
                best_pattern = {
                    'type': 'Cup-with-Handle',
                    'start_date': dates[i].strftime('%Y-%m-%d'),
                    'end_date': dates[min(handle_end - 1, len(df) - 1)].strftime('%Y-%m-%d'),
                    'left_peak': float(left_peak),
                    'left_peak_date': dates[i + left_peak_rel].strftime('%Y-%m-%d'),
                    'cup_low': float(cup_low),
                    'cup_low_date': dates[i + cup_low_rel].strftime('%Y-%m-%d'),
                    'right_peak': float(right_peak),
                    'right_peak_date': dates[i + right_peak_rel].strftime('%Y-%m-%d'),
                    'handle_low': float(handle_low),
                    'depth_pct': round(depth_pct, 1),
                    'handle_depth_pct': round(handle_depth, 1),
                    'duration_weeks': end_idx - i,
                    'pivot_point': round(float(pivot_point), 2),
                    'handle_in_upper_half': handle_in_upper_half,
                    'volume_dryup_in_handle': vol_dryup,
                    'u_shape': int(weeks_near_bottom),
                    'quality_score': quality
                }

    if best_pattern:
        patterns.append(best_pattern)

    return patterns


def _calculate_cup_quality(depth, handle_depth, vol_dryup,
                           weeks_at_bottom, duration, handle_in_upper_half):
    """오닐 기준 Cup-with-Handle 품질 점수 (0~100)"""
    score = 50

    # 깊이: 12~25%가 이상적
    if 12 <= depth <= 25:
        score += 15
    elif 25 < depth <= 33:
        score += 5
    else:
        score -= 10

    # 핸들 깊이: 8~12%가 이상적
    if handle_depth <= 12:
        score += 10
    elif handle_depth <= 15:
        score += 5

    # 거래량 건조
    if vol_dryup:
        score += 15

    # U자형 바닥
    if weeks_at_bottom >= 3:
        score += 10
    elif weeks_at_bottom >= 2:
        score += 5

    # 핸들 위치
    if handle_in_upper_half:
        score += 10

    # 기간 (7-30주가 이상적)
    if 7 <= duration <= 30:
        score += 5

    return min(100, max(0, score))


# ====================================================================
# 2. Double Bottom 패턴 감지
# ====================================================================

def detect_double_bottom(df: pd.DataFrame, min_weeks: int = 7, max_weeks: int = 65) -> List[Dict]:
    """
    Double Bottom (W 패턴) 감지

    오닐의 정의:
    - W자 형태
    - 두 번째 바닥이 첫 번째 바닥과 같거나 약간 아래(1~2포인트)
    - 피벗 포인트: W의 가운데 고점

    Args:
        df: 주봉 OHLCV 데이터프레임
        min_weeks: 최소 기간 (주)
        max_weeks: 최대 기간 (주)

    Returns:
        감지된 패턴 리스트
    """
    patterns = []

    if len(df) < min_weeks:
        return patterns

    highs = df['High'].values
    lows = df['Low'].values
    closes = df['Close'].values
    dates = df.index

    best_pattern = None
    best_quality = 0

    for i in range(max(0, len(df) - max_weeks - 5), len(df) - min_weeks):
        for duration in range(min_weeks, min(max_weeks + 1, len(df) - i)):
            end_idx = i + duration
            if end_idx >= len(df):
                break

            window_highs = highs[i:end_idx]
            window_lows = lows[i:end_idx]

            half = len(window_lows) // 2

            # 1. 시작 고점 (A)
            start_peak = np.max(window_highs[:max(3, half // 2)])

            # 2. 첫 번째 바닥 (B)
            bottom1_rel = np.argmin(window_lows[:half + 2])
            bottom1 = window_lows[bottom1_rel]

            # 3. 가운데 고점 (C) - W의 중간 봉우리
            mid_start = bottom1_rel + 1
            mid_end = min(mid_start + half, len(window_highs))
            if mid_start >= mid_end:
                continue

            mid_section = window_highs[mid_start:mid_end]
            middle_peak_rel = mid_start + np.argmax(mid_section)
            middle_peak = window_highs[middle_peak_rel]

            # 4. 두 번째 바닥 (D)
            second_start = middle_peak_rel + 1
            if second_start >= len(window_lows):
                continue

            bottom2_rel = second_start + np.argmin(window_lows[second_start:])
            bottom2 = window_lows[bottom2_rel]

            # 5. 두 번째 바닥이 첫 번째와 비슷한지 확인
            undercut_pct = ((bottom1 - bottom2) / bottom1) * 100
            if undercut_pct < -5 or undercut_pct > 10:
                continue

            # 6. 깊이 확인
            depth = ((start_peak - min(bottom1, bottom2)) / start_peak) * 100
            if depth < 12 or depth > 50:
                continue

            # 7. 가운데 고점이 충분히 반등했는지 확인
            bounce_pct = ((middle_peak - bottom1) / bottom1) * 100
            if bounce_pct < 5:
                continue

            # 피벗 포인트 = W 가운데 고점
            pivot_point = middle_peak

            # 품질 점수
            quality = 50
            if 12 <= depth <= 25:
                quality += 15
            elif 25 < depth <= 33:
                quality += 5
            if bottom2 <= bottom1:  # undercut (좋은 신호)
                quality += 10
            if 7 <= duration <= 40:
                quality += 5
            if bounce_pct >= 10:
                quality += 10

            if quality > best_quality:
                best_quality = quality
                best_pattern = {
                    'type': 'Double Bottom',
                    'start_date': dates[i].strftime('%Y-%m-%d'),
                    'end_date': dates[min(end_idx - 1, len(df) - 1)].strftime('%Y-%m-%d'),
                    'bottom1': float(bottom1),
                    'bottom1_date': dates[i + bottom1_rel].strftime('%Y-%m-%d'),
                    'bottom2': float(bottom2),
                    'bottom2_date': dates[i + bottom2_rel].strftime('%Y-%m-%d'),
                    'middle_peak': float(middle_peak),
                    'middle_peak_date': dates[i + middle_peak_rel].strftime('%Y-%m-%d'),
                    'pivot_point': round(float(pivot_point), 2),
                    'depth_pct': round(depth, 1),
                    'undercut': bool(bottom2 < bottom1),
                    'undercut_pct': round(undercut_pct, 1),
                    'duration_weeks': duration,
                    'quality_score': min(100, max(0, quality))
                }

    if best_pattern:
        patterns.append(best_pattern)

    return patterns


# ====================================================================
# 3. Flat Base 감지
# ====================================================================

def detect_flat_base(df: pd.DataFrame, min_weeks: int = 5) -> List[Dict]:
    """
    Flat Base 감지 - 이전 돌파 후 횡보

    오닐의 정의:
    - 조정폭 10~15% 이내
    - 최소 5~6주
    - 이전에 20%+ 상승이 있었어야 함

    Args:
        df: 주봉 OHLCV 데이터프레임
        min_weeks: 최소 기간 (주)

    Returns:
        감지된 패턴 리스트
    """
    patterns = []

    if len(df) < min_weeks + 20:
        return patterns

    highs = df['High'].values
    lows = df['Low'].values
    closes = df['Close'].values
    dates = df.index

    best_pattern = None
    best_quality = 0

    for end in range(min_weeks, min(30, len(df))):
        for start in range(max(0, end - 25), end - min_weeks + 1):
            window_highs = highs[len(df) - end:len(df) - start] if start > 0 else highs[len(df) - end:]
            window_lows = lows[len(df) - end:len(df) - start] if start > 0 else lows[len(df) - end:]

            if len(window_highs) < min_weeks:
                continue

            high = np.max(window_highs)
            low = np.min(window_lows)
            correction = ((high - low) / high) * 100

            if correction > 15:
                continue

            # 이전에 20%+ 상승이 있었는지 확인
            prior_end = len(df) - end
            prior_start = max(0, prior_end - 20)
            if prior_start >= prior_end:
                continue

            prior_low = np.min(lows[prior_start:prior_end])
            prior_gain = ((closes[prior_end] - prior_low) / prior_low) * 100

            if prior_gain < 20:
                continue

            # 품질 점수
            quality = 50
            if correction <= 10:
                quality += 15
            elif correction <= 12:
                quality += 10
            else:
                quality += 5
            if prior_gain >= 30:
                quality += 10
            if len(window_highs) >= 6:
                quality += 5

            actual_start_idx = len(df) - end
            actual_end_idx = (len(df) - start - 1) if start > 0 else (len(df) - 1)

            if quality > best_quality:
                best_quality = quality
                best_pattern = {
                    'type': 'Flat Base',
                    'start_date': dates[actual_start_idx].strftime('%Y-%m-%d'),
                    'end_date': dates[actual_end_idx].strftime('%Y-%m-%d'),
                    'high': float(high),
                    'low': float(low),
                    'correction_pct': round(correction, 1),
                    'duration_weeks': len(window_highs),
                    'pivot_point': round(float(high), 2),
                    'prior_gain_pct': round(prior_gain, 1),
                    'quality_score': min(100, max(0, quality))
                }

    if best_pattern:
        patterns.append(best_pattern)

    return patterns


# ====================================================================
# 4. High Tight Flag 감지
# ====================================================================

def detect_high_tight_flag(df: pd.DataFrame) -> List[Dict]:
    """
    High Tight Flag - 매우 드문 강력한 패턴

    오닐의 정의:
    - 4~8주 내 100%+ 상승
    - 이후 3~5주 횡보, 조정 10~25% 이내

    Args:
        df: 주봉 OHLCV 데이터프레임

    Returns:
        감지된 패턴 리스트
    """
    patterns = []

    if len(df) < 12:
        return patterns

    highs = df['High'].values
    lows = df['Low'].values
    dates = df.index

    for i in range(8, len(df) - 3):
        for lookback in range(4, 9):
            if i - lookback < 0:
                continue

            start_price = lows[i - lookback]
            peak_price = np.max(highs[i - lookback:i + 1])
            gain = ((peak_price - start_price) / start_price) * 100

            if gain < 100:
                continue

            # 이후 3~5주 횡보 확인
            flag_end = min(i + 6, len(df))
            if flag_end - i < 3:
                continue

            flag_lows = lows[i:flag_end]
            flag_low = np.min(flag_lows)
            flag_correction = ((peak_price - flag_low) / peak_price) * 100

            if 10 <= flag_correction <= 25:
                patterns.append({
                    'type': 'High Tight Flag',
                    'start_date': dates[i - lookback].strftime('%Y-%m-%d'),
                    'end_date': dates[flag_end - 1].strftime('%Y-%m-%d'),
                    'surge_pct': round(gain, 1),
                    'surge_weeks': lookback,
                    'flag_correction_pct': round(flag_correction, 1),
                    'flag_weeks': flag_end - i,
                    'pivot_point': round(float(peak_price), 2),
                    'rarity': 'VERY RARE - strongest pattern',
                    'quality_score': 90  # HTF는 기본적으로 높은 품질
                })

    return patterns


# ====================================================================
# 5. 거래량 분석
# ====================================================================

def analyze_volume(df: pd.DataFrame) -> Dict:
    """
    오닐 스타일 거래량 분석

    Args:
        df: 주봉 OHLCV 데이터프레임

    Returns:
        거래량 분석 결과 딕셔너리
    """
    vol_avg = df['Volume'].rolling(10).mean()  # 10주 평균 거래량

    results = {
        'accumulation_weeks': 0,
        'distribution_weeks': 0,
        'recent_volume_trend': 'NEUTRAL',
        'volume_surges': [],
        'volume_dryups': [],
        'last_5_weeks_summary': []
    }

    if len(df) < 11:
        return results

    for i in range(10, len(df)):
        vol = df['Volume'].iloc[i]
        avg = vol_avg.iloc[i]

        if pd.isna(avg) or avg == 0:
            continue

        vol_pct = ((vol - avg) / avg) * 100
        price_change = ((df['Close'].iloc[i] - df['Close'].iloc[i - 1]) / df['Close'].iloc[i - 1]) * 100

        # 축적주 (상승 + 거래량 증가)
        if price_change > 0.5 and vol > avg:
            results['accumulation_weeks'] += 1

        # 분배주 (하락 + 거래량 증가)
        if price_change < -0.2 and vol > avg:
            results['distribution_weeks'] += 1

        # 거래량 급증 (50%+ 증가)
        if vol_pct >= 50:
            results['volume_surges'].append({
                'date': df.index[i].strftime('%Y-%m-%d'),
                'vol_pct_above_avg': round(vol_pct, 1),
                'price_change_pct': round(price_change, 1),
                'signal': 'BREAKOUT' if price_change > 1 else 'DISTRIBUTION' if price_change < -0.5 else 'NEUTRAL'
            })

        # 거래량 건조 (50% 이하)
        if vol_pct <= -50:
            results['volume_dryups'].append({
                'date': df.index[i].strftime('%Y-%m-%d'),
                'vol_pct_below_avg': round(abs(vol_pct), 1)
            })

    # 최근 5주 요약
    for i in range(max(10, len(df) - 5), len(df)):
        vol = df['Volume'].iloc[i]
        avg = vol_avg.iloc[i]
        if pd.isna(avg) or avg == 0:
            continue

        vol_pct = ((vol - avg) / avg) * 100
        price_change = ((df['Close'].iloc[i] - df['Close'].iloc[i - 1]) / df['Close'].iloc[i - 1]) * 100

        results['last_5_weeks_summary'].append({
            'date': df.index[i].strftime('%Y-%m-%d'),
            'close': round(float(df['Close'].iloc[i]), 2),
            'vol_vs_avg': f"{vol_pct:+.0f}%",
            'price_change': f"{price_change:+.1f}%"
        })

    # 최근 추세 판단 (최근 4주)
    recent_acc = 0
    recent_dist = 0
    for i in range(max(10, len(df) - 4), len(df)):
        vol = df['Volume'].iloc[i]
        avg = vol_avg.iloc[i]
        if pd.isna(avg):
            continue
        price_change = ((df['Close'].iloc[i] - df['Close'].iloc[i - 1]) / df['Close'].iloc[i - 1]) * 100
        if price_change > 0.5 and vol > avg:
            recent_acc += 1
        if price_change < -0.2 and vol > avg:
            recent_dist += 1

    if recent_acc > recent_dist + 1:
        results['recent_volume_trend'] = 'ACCUMULATION'
    elif recent_dist > recent_acc + 1:
        results['recent_volume_trend'] = 'DISTRIBUTION'
    else:
        results['recent_volume_trend'] = 'NEUTRAL'

    return results


# ====================================================================
# 6. Base Stage 카운팅
# ====================================================================

def count_base_stage(df: pd.DataFrame) -> Dict:
    """
    Base Stage 추정
    1단계: 가장 강력 (IPO 후 첫 base 또는 장기 하락 후 첫 상승)
    2단계: 여전히 유효
    3~4단계: 위험 증가

    간단한 휴리스틱: 최근 2년 내 주요 돌파 횟수로 추정

    Args:
        df: 주봉 OHLCV 데이터프레임

    Returns:
        단계 정보 딕셔너리
    """
    if len(df) < 20:
        return {'estimated_stage': 1, 'breakout_count': 0, 'warning': None}

    closes = df['Close'].values
    highs = df['High'].values

    # 20주 이동평균 기준 주요 돌파 횟수
    ma20 = pd.Series(closes).rolling(20).mean().values

    breakout_count = 0
    in_base = False
    base_high = 0

    for i in range(20, len(df)):
        if pd.isna(ma20[i]):
            continue

        # 신고가 돌파 감지
        lookback_high = np.max(highs[max(0, i - 52):i])

        if closes[i] > lookback_high and closes[i] > ma20[i]:
            if in_base:
                breakout_count += 1
                in_base = False

        # 조정(base) 진입 감지
        if not in_base and closes[i] < highs[i] * 0.88:  # 12% 이상 조정
            in_base = True
            base_high = highs[i]

    stage = min(4, breakout_count + 1)

    warning = None
    if stage >= 3:
        warning = (
            f"CAUTION: Estimated Stage {stage} base. "
            "Late-stage bases have significantly higher failure rates. "
            "Most big winners come from 1st and 2nd stage bases."
        )

    return {
        'estimated_stage': stage,
        'breakout_count': breakout_count,
        'warning': warning
    }


# ====================================================================
# 7. 불량 패턴 체크
# ====================================================================

def check_pattern_faults(pattern: Dict, df: pd.DataFrame) -> List[str]:
    """
    오닐이 경고한 불량 패턴 특징 체크

    Args:
        pattern: 감지된 패턴 딕셔너리
        df: 주봉 OHLCV 데이터프레임

    Returns:
        불량 요인 리스트
    """
    faults = []

    # 1. 깊이 과다 (33% 이상이면 주의, 50% 이상이면 심각)
    depth = pattern.get('depth_pct', 0)
    if depth > 50:
        faults.append(f"EXCESSIVE DEPTH ({depth:.0f}%): Corrections over 50% have much higher failure rate.")
    elif depth > 33:
        faults.append(f"DEEP CORRECTION ({depth:.0f}%): Over 33% correction in bull market is concerning.")

    # 2. 핸들 관련 (Cup-with-Handle만)
    if pattern.get('type') == 'Cup-with-Handle':
        if pattern.get('handle_in_upper_half') is False:
            faults.append("HANDLE IN LOWER HALF: Handle below midpoint of base. Weak demand signal.")

        handle_depth = pattern.get('handle_depth_pct', 0)
        if handle_depth > 12:
            faults.append(f"DEEP HANDLE ({handle_depth:.0f}%): Handle ideally 8-12%. Deeper handles are less reliable.")

        if not pattern.get('volume_dryup_in_handle', True):
            faults.append("NO VOLUME DRY-UP IN HANDLE: Volume should decrease in handle (shows selling exhaustion).")

    # 3. U자형 부족
    u_shape = pattern.get('u_shape', 0)
    if isinstance(u_shape, (int, float)) and u_shape < 2:
        faults.append("V-SHAPED BOTTOM: Quick bounce without time to shake out weak holders. Higher risk.")

    # 4. Wide and Loose 체크
    try:
        start_date = pd.Timestamp(pattern.get('start_date'))
        end_date = pd.Timestamp(pattern.get('end_date'))
        mask = (df.index >= start_date) & (df.index <= end_date)
        pattern_df = df.loc[mask]

        if len(pattern_df) > 0:
            weekly_ranges = ((pattern_df['High'] - pattern_df['Low']) / pattern_df['Close']).mean() * 100
            if weekly_ranges > 15:
                faults.append(f"WIDE AND LOOSE: Average weekly range {weekly_ranges:.1f}%. Too volatile, failure-prone.")
    except Exception:
        pass

    return faults


# ====================================================================
# 8. 메인 분석 함수 (통합)
# ====================================================================

def run_pattern_detection(df: pd.DataFrame) -> Dict:
    """
    전체 패턴 감지 파이프라인 실행

    Args:
        df: 주봉 OHLCV 데이터프레임

    Returns:
        종합 분석 결과 딕셔너리
    """
    print("[*] Running code-based pattern detection...")

    # 모든 패턴 감지
    all_patterns = []

    print("  - Detecting Cup-with-Handle...")
    cup_patterns = detect_cup_with_handle(df)
    all_patterns.extend(cup_patterns)

    print("  - Detecting Double Bottom...")
    db_patterns = detect_double_bottom(df)
    all_patterns.extend(db_patterns)

    print("  - Detecting Flat Base...")
    fb_patterns = detect_flat_base(df)
    all_patterns.extend(fb_patterns)

    print("  - Detecting High Tight Flag...")
    htf_patterns = detect_high_tight_flag(df)
    all_patterns.extend(htf_patterns)

    # 최고 품질 패턴 선택
    best_pattern = None
    if all_patterns:
        best_pattern = max(all_patterns, key=lambda p: p.get('quality_score', 0))
        print(f"  [OK] Best pattern: {best_pattern['type']} (quality: {best_pattern['quality_score']})")
    else:
        print("  [--] No clear pattern detected")

    # 불량 패턴 체크
    faults = []
    if best_pattern:
        faults = check_pattern_faults(best_pattern, df)
        if faults:
            print(f"  [!] {len(faults)} fault(s) detected")

    # 거래량 분석
    print("  - Analyzing volume...")
    volume_analysis = analyze_volume(df)

    # Base Stage 추정
    print("  - Counting base stage...")
    stage_info = count_base_stage(df)

    # 결과 종합
    result = {
        'all_patterns': all_patterns,
        'best_pattern': best_pattern,
        'pattern_faults': faults,
        'volume_analysis': volume_analysis,
        'base_stage': stage_info,
        'summary': _generate_summary(best_pattern, faults, volume_analysis, stage_info, df)
    }

    print("[OK] Pattern detection complete!")
    return result


def _generate_summary(pattern: Optional[Dict], faults: List[str],
                      volume: Dict, stage: Dict, df: pd.DataFrame) -> str:
    """패턴 감지 결과를 AI에게 전달할 텍스트 요약 생성"""

    lines = []
    lines.append("=" * 60)
    lines.append("CODE-BASED PATTERN DETECTION RESULTS")
    lines.append("=" * 60)

    # 패턴 정보
    if pattern:
        lines.append(f"\nDETECTED PATTERN: {pattern['type']}")
        lines.append(f"Quality Score: {pattern.get('quality_score', 0)}/100")
        lines.append(f"Period: {pattern.get('start_date')} to {pattern.get('end_date')}")
        lines.append(f"Duration: {pattern.get('duration_weeks', 'N/A')} weeks")

        if pattern['type'] == 'Cup-with-Handle':
            lines.append(f"Cup Depth: {pattern.get('depth_pct', 0):.1f}%")
            lines.append(f"Handle Depth: {pattern.get('handle_depth_pct', 0):.1f}%")
            lines.append(f"Left Peak: ${pattern.get('left_peak', 0):.2f} ({pattern.get('left_peak_date')})")
            lines.append(f"Cup Low: ${pattern.get('cup_low', 0):.2f} ({pattern.get('cup_low_date')})")
            lines.append(f"Right Peak: ${pattern.get('right_peak', 0):.2f} ({pattern.get('right_peak_date')})")
            lines.append(f"Handle in Upper Half: {'Yes' if pattern.get('handle_in_upper_half') else 'No'}")
            lines.append(f"Volume Dry-up in Handle: {'Yes' if pattern.get('volume_dryup_in_handle') else 'No'}")
            lines.append(f"U-Shape Bottom: {pattern.get('u_shape', 0)} weeks near bottom")

        elif pattern['type'] == 'Double Bottom':
            lines.append(f"Depth: {pattern.get('depth_pct', 0):.1f}%")
            lines.append(f"Bottom 1: ${pattern.get('bottom1', 0):.2f} ({pattern.get('bottom1_date')})")
            lines.append(f"Bottom 2: ${pattern.get('bottom2', 0):.2f} ({pattern.get('bottom2_date')})")
            lines.append(f"Middle Peak: ${pattern.get('middle_peak', 0):.2f}")
            lines.append(f"Undercut: {'Yes' if pattern.get('undercut') else 'No'} ({pattern.get('undercut_pct', 0):.1f}%)")

        elif pattern['type'] == 'Flat Base':
            lines.append(f"Correction: {pattern.get('correction_pct', 0):.1f}%")
            lines.append(f"Prior Gain: {pattern.get('prior_gain_pct', 0):.1f}%")

        elif pattern['type'] == 'High Tight Flag':
            lines.append(f"Surge: {pattern.get('surge_pct', 0):.1f}% in {pattern.get('surge_weeks')} weeks")
            lines.append(f"Flag Correction: {pattern.get('flag_correction_pct', 0):.1f}%")

        lines.append(f"PIVOT POINT (Buy Point): ${pattern.get('pivot_point', 0):.2f}")
        lines.append(f"STOP LOSS (7-8% below): ${pattern.get('pivot_point', 0) * 0.92:.2f}")
    else:
        lines.append("\nNO CLEAR PATTERN DETECTED")
        lines.append("The stock may be in a consolidation phase, downtrend, or extended run.")

    # 불량 패턴 경고
    if faults:
        lines.append(f"\nPATTERN FAULTS ({len(faults)}):")
        for fault in faults:
            lines.append(f"  [!] {fault}")

    # 거래량 분석
    lines.append(f"\nVOLUME ANALYSIS:")
    lines.append(f"Accumulation Weeks: {volume.get('accumulation_weeks', 0)}")
    lines.append(f"Distribution Weeks: {volume.get('distribution_weeks', 0)}")
    lines.append(f"Recent Trend: {volume.get('recent_volume_trend', 'N/A')}")

    if volume.get('volume_surges'):
        recent_surges = volume['volume_surges'][-3:]
        lines.append(f"Recent Volume Surges:")
        for s in recent_surges:
            lines.append(f"  {s['date']}: +{s['vol_pct_above_avg']:.0f}% vol, {s['price_change_pct']:+.1f}% price ({s['signal']})")

    if volume.get('last_5_weeks_summary'):
        lines.append(f"\nLast 5 Weeks:")
        for w in volume['last_5_weeks_summary']:
            lines.append(f"  {w['date']}: ${w['close']} | Vol {w['vol_vs_avg']} avg | Price {w['price_change']}")

    # Base Stage
    lines.append(f"\nBASE STAGE: Estimated Stage {stage.get('estimated_stage', 'N/A')}")
    if stage.get('warning'):
        lines.append(f"  [!] {stage['warning']}")

    lines.append("=" * 60)

    return "\n".join(lines)
