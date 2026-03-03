# O'Neil Style Chart Pattern Analysis — 기술 설계 문서

## 개요

이 문서는 윌리엄 오닐의 차트 분석 방법론을 AI가 자동으로 수행할 수 있도록 설계한 기술 사양서입니다.
PDF 17~127페이지의 오닐 직접 분석 차트를 기반으로, 다음을 자동화합니다:

1. **차트 패턴 감지** (Cup-with-Handle, Double Bottom, Flat Base 등)
2. **거래량 분석** (급증, 건조, 분배일)
3. **매수/매도 포인트 자동 표시**
4. **Base 영역 자동 표시**
5. **이동평균선 및 상대강도 분석**

---

## 접근 방식: 2가지 전략

### 전략 A: 코드 기반 패턴 감지 (추천 — 정확하고 재현 가능)

주가/거래량 데이터를 코드로 분석하여 패턴을 프로그래밍적으로 감지합니다.
AI는 감지된 패턴을 오닐의 관점에서 해석하고 설명합니다.

```
주가 데이터 (OHLCV) → Python 패턴 감지 엔진 → 감지 결과 + 차트 생성
                                                      ↓
                                              AI (오닐 페르소나)가 해석/설명
```

### 전략 B: 멀티모달 AI 차트 이미지 분석 (보조적 활용)

차트 이미지를 GPT-4V, Claude Vision, Gemini Pro Vision 등에 직접 보여주고 분석하게 합니다.
현재 멀티모달 AI의 차트 패턴 인식 정확도는 제한적이므로 전략 A의 보조 수단으로만 사용합니다.

**권장: 전략 A를 메인으로, 전략 B를 보조로 사용**

---

## 전략 A 상세 설계: 코드 기반 패턴 감지 엔진

### 1. 필요 데이터

```python
# 최소 필요: 주간(Weekly) OHLCV 데이터, 최소 52주 이상
# 이상적: 일간(Daily) + 주간(Weekly) OHLCV, 2~3년치

data = {
    "date": [],        # 날짜
    "open": [],        # 시가
    "high": [],        # 고가
    "low": [],         # 저가
    "close": [],       # 종가
    "volume": [],      # 거래량
}
```

### 데이터 소스 옵션
| 소스 | 비용 | 한국 주식 | 미국 주식 | 비고 |
|------|------|-----------|-----------|------|
| Yahoo Finance (yfinance) | 무료 | △ | ✅ | 가장 쉬운 시작점 |
| Alpha Vantage | 무료/유료 | ✗ | ✅ | API key 필요 |
| 한국투자증권 OpenAPI | 무료 | ✅ | ✅ | 한국 주식 필수 |
| KRX 데이터 | 무료 | ✅ | ✗ | 공공데이터 |
| Twelve Data | 유료 | ✗ | ✅ | 정확한 데이터 |

---

### 2. 핵심 지표 계산

```python
import numpy as np
import pandas as pd

def calculate_indicators(df):
    """오닐 분석에 필요한 핵심 지표 계산"""
    
    # 이동평균선 (O'Neil이 사용하는 것들)
    df['ma_10w'] = df['close'].rolling(50).mean()   # 10주 = 50일 이동평균
    df['ma_30w'] = df['close'].rolling(150).mean()  # 30주 = 150일 이동평균
    df['ma_40w'] = df['close'].rolling(200).mean()  # 40주 = 200일 이동평균
    
    # 거래량 이동평균 (50일)
    df['vol_avg_50'] = df['volume'].rolling(50).mean()
    
    # 거래량 변화율 (% above/below average)
    df['vol_pct_change'] = ((df['volume'] - df['vol_avg_50']) / df['vol_avg_50']) * 100
    
    # 상대강도 (Relative Strength) - 시장 대비
    # RS Rating 계산은 전체 시장 대비 52주 가격 성과 기반
    df['price_change_52w'] = df['close'].pct_change(252) * 100
    
    # 주간 가격 범위 (tightness 측정용)
    df['weekly_range_pct'] = ((df['high'] - df['low']) / df['close']) * 100
    
    return df
```

---

### 3. 패턴 감지 알고리즘

#### 3-1. Cup-with-Handle 패턴 감지

오닐의 정의 기준:
- 기간: 7주 ~ 65주 (대부분 3~6개월)
- 깊이: 12% ~ 33% (강세장), 최대 50% (약세장)
- 바닥: "U" 모양 (V 모양은 위험)
- 핸들: 상단 1/2에 형성, 하락 8~12% 이내, 하향 드리프트
- 핸들이 10주 이동평균 위에 있어야 함
- 돌파 거래량: 평균 대비 50%+ 증가

```python
def detect_cup_with_handle(df, min_weeks=7, max_weeks=65):
    """
    Cup-with-Handle 패턴 감지
    
    Returns: list of detected patterns with metadata
    """
    patterns = []
    weekly = df.resample('W').agg({
        'open': 'first', 'high': 'max', 'low': 'min', 
        'close': 'last', 'volume': 'sum'
    })
    
    for i in range(len(weekly) - min_weeks):
        for duration in range(min_weeks, min(max_weeks, len(weekly) - i)):
            window = weekly.iloc[i:i+duration]
            
            # 1. 시작점(왼쪽 고점) 찾기
            left_peak = window['high'].iloc[:5].max()
            left_peak_idx = window['high'].iloc[:5].idxmax()
            
            # 2. 바닥 찾기
            cup_low = window['low'].min()
            cup_low_idx = window['low'].idxmin()
            
            # 3. 깊이 계산
            depth_pct = ((left_peak - cup_low) / left_peak) * 100
            
            # 깊이 필터: 12% ~ 33% (강세장 기준)
            if depth_pct < 12 or depth_pct > 50:
                continue
            
            # 4. U자형 검증 (V자형 배제)
            # 바닥 부근에서 최소 2~3주 머물러야 함
            bottom_zone = cup_low * 1.03  # 바닥에서 3% 이내
            weeks_near_bottom = (window['low'] <= bottom_zone).sum()
            if weeks_near_bottom < 2:
                continue  # V자형일 가능성 높음
            
            # 5. 오른쪽 고점 찾기 (핸들 시작점)
            right_section = window.iloc[window.index.get_loc(cup_low_idx):]
            if len(right_section) < 3:
                continue
            right_peak = right_section['high'].max()
            right_peak_idx = right_section['high'].idxmax()
            
            # 6. 핸들 감지
            handle = weekly.loc[right_peak_idx:]
            if len(handle) < 2:
                continue
            
            handle_window = handle.iloc[:min(10, len(handle))]
            handle_low = handle_window['low'].min()
            handle_depth = ((right_peak - handle_low) / right_peak) * 100
            
            # 핸들 깊이: 8~12% 이내 (강세장)
            if handle_depth > 15:
                continue
            
            # 핸들이 전체 base 상단 1/2에 있는지 확인
            base_midpoint = cup_low + (left_peak - cup_low) / 2
            if handle_low < base_midpoint:
                continue  # 핸들이 하단에 있으면 불량
            
            # 7. 핸들에서 거래량 감소 확인
            handle_avg_vol = handle_window['volume'].mean()
            base_avg_vol = window['volume'].mean()
            vol_dryup = handle_avg_vol < base_avg_vol * 0.8
            
            # 8. 피벗 포인트 계산
            pivot_point = right_peak  # 핸들 고점 + $0.10
            
            patterns.append({
                'type': 'cup_with_handle',
                'start_date': window.index[0],
                'end_date': handle_window.index[-1],
                'left_peak': left_peak,
                'cup_low': cup_low,
                'depth_pct': depth_pct,
                'duration_weeks': duration,
                'pivot_point': pivot_point,
                'handle_depth_pct': handle_depth,
                'handle_in_upper_half': True,
                'volume_dryup_in_handle': vol_dryup,
                'u_shape': weeks_near_bottom >= 2,
                'quality_score': calculate_pattern_quality(
                    depth_pct, handle_depth, vol_dryup, 
                    weeks_near_bottom, duration
                )
            })
    
    return patterns


def calculate_pattern_quality(depth, handle_depth, vol_dryup, 
                               weeks_at_bottom, duration):
    """
    오닐 기준 패턴 품질 점수 (0~100)
    """
    score = 50  # 기본 점수
    
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
    
    return min(100, max(0, score))
```

#### 3-2. Double Bottom 패턴 감지

오닐의 정의:
- W자 형태
- 두 번째 바닥이 첫 번째 바닥과 같거나 약간 아래(1~2포인트)
- 피벗 포인트: W의 가운데 고점

```python
def detect_double_bottom(df, min_weeks=7, max_weeks=65):
    """Double Bottom (W 패턴) 감지"""
    patterns = []
    weekly = df.resample('W').agg({
        'open': 'first', 'high': 'max', 'low': 'min',
        'close': 'last', 'volume': 'sum'
    })
    
    for i in range(len(weekly) - min_weeks):
        for duration in range(min_weeks, min(max_weeks, len(weekly) - i)):
            window = weekly.iloc[i:i+duration]
            
            # W 형태 찾기: Peak → Bottom1 → Middle Peak → Bottom2 → Rise
            
            # 1. 첫 번째 바닥 (B)
            first_half = window.iloc[:duration//2 + 2]
            bottom1 = first_half['low'].min()
            bottom1_idx = first_half['low'].idxmin()
            
            # 2. 가운데 고점 (C) - W의 중간 봉우리
            middle_section = window.iloc[
                window.index.get_loc(bottom1_idx):
            ]
            if len(middle_section) < 4:
                continue
            middle_peak = middle_section.iloc[:len(middle_section)//2+2]['high'].max()
            middle_peak_idx = middle_section.iloc[:len(middle_section)//2+2]['high'].idxmax()
            
            # 3. 두 번째 바닥 (D)
            second_section = window.loc[middle_peak_idx:]
            if len(second_section) < 2:
                continue
            bottom2 = second_section['low'].min()
            bottom2_idx = second_section['low'].idxmin()
            
            # 4. 두 번째 바닥이 첫 번째와 같거나 약간 아래인지 확인
            # 오닐: "거의 모든 경우 1~2포인트 아래로 undercut"
            undercut_pct = ((bottom1 - bottom2) / bottom1) * 100
            if undercut_pct < -5 or undercut_pct > 10:
                continue  # 너무 다르면 W가 아님
            
            # 5. 깊이 확인
            start_peak = window['high'].iloc[:3].max()
            depth = ((start_peak - min(bottom1, bottom2)) / start_peak) * 100
            if depth < 12 or depth > 50:
                continue
            
            # 6. 피벗 포인트 = W 가운데 고점
            pivot_point = middle_peak
            
            patterns.append({
                'type': 'double_bottom',
                'start_date': window.index[0],
                'end_date': window.index[-1],
                'bottom1': bottom1,
                'bottom1_date': bottom1_idx,
                'bottom2': bottom2,
                'bottom2_date': bottom2_idx,
                'middle_peak': middle_peak,
                'pivot_point': pivot_point,
                'depth_pct': depth,
                'undercut': bottom2 < bottom1,
                'duration_weeks': duration
            })
    
    return patterns
```

#### 3-3. Flat Base 감지

```python
def detect_flat_base(df, min_weeks=5):
    """Flat Base 감지 — 이전 돌파 후 횡보"""
    patterns = []
    weekly = df.resample('W').agg({
        'open': 'first', 'high': 'max', 'low': 'min',
        'close': 'last', 'volume': 'sum'
    })
    
    for i in range(min_weeks, len(weekly)):
        window = weekly.iloc[i-min_weeks:i]
        
        high = window['high'].max()
        low = window['low'].min()
        correction = ((high - low) / high) * 100
        
        # Flat base: 조정폭 10~15% 이내, 최소 5~6주
        if correction <= 15 and len(window) >= 5:
            # 이전에 20%+ 상승이 있었는지 확인
            prior = weekly.iloc[max(0,i-min_weeks-20):i-min_weeks]
            if len(prior) > 0:
                prior_low = prior['low'].min()
                prior_gain = ((window['close'].iloc[0] - prior_low) / prior_low) * 100
                
                if prior_gain >= 20:
                    patterns.append({
                        'type': 'flat_base',
                        'start_date': window.index[0],
                        'end_date': window.index[-1],
                        'high': high,
                        'low': low,
                        'correction_pct': correction,
                        'duration_weeks': len(window),
                        'pivot_point': high,
                        'prior_gain_pct': prior_gain
                    })
    
    return patterns
```

#### 3-4. High Tight Flag 감지

```python
def detect_high_tight_flag(df):
    """High Tight Flag — 매우 드문 강력한 패턴"""
    patterns = []
    weekly = df.resample('W').agg({
        'open': 'first', 'high': 'max', 'low': 'min',
        'close': 'last', 'volume': 'sum'
    })
    
    for i in range(8, len(weekly)):
        # 4~8주 내 100%+ 상승 확인
        for lookback in range(4, 9):
            if i - lookback < 0:
                continue
            
            surge_window = weekly.iloc[i-lookback:i]
            start_price = surge_window['low'].iloc[0]
            peak_price = surge_window['high'].max()
            gain = ((peak_price - start_price) / start_price) * 100
            
            if gain < 100:
                continue
            
            # 이후 3~5주 횡보, 조정 10~25% 이내
            flag_end = min(i + 5, len(weekly))
            flag_window = weekly.iloc[i:flag_end]
            
            if len(flag_window) < 3:
                continue
            
            flag_low = flag_window['low'].min()
            flag_correction = ((peak_price - flag_low) / peak_price) * 100
            
            if 10 <= flag_correction <= 25:
                patterns.append({
                    'type': 'high_tight_flag',
                    'start_date': surge_window.index[0],
                    'end_date': flag_window.index[-1],
                    'surge_pct': gain,
                    'surge_weeks': lookback,
                    'flag_correction_pct': flag_correction,
                    'flag_weeks': len(flag_window),
                    'pivot_point': peak_price,
                    'rarity': 'VERY RARE — strongest pattern'
                })
    
    return patterns
```

---

### 4. 거래량 분석 모듈

```python
def analyze_volume(df):
    """오닐 스타일 거래량 분석"""
    
    df['vol_avg_50'] = df['volume'].rolling(50).mean()
    
    results = {
        'volume_surges': [],      # 거래량 급증일
        'volume_dryups': [],      # 거래량 건조일
        'distribution_days': [],  # 분배일 (하락 + 거래량 증가)
        'accumulation_days': [],  # 축적일 (상승 + 거래량 증가)
    }
    
    for i in range(1, len(df)):
        row = df.iloc[i]
        prev = df.iloc[i-1]
        vol_pct = ((row['volume'] - df['vol_avg_50'].iloc[i]) / 
                   df['vol_avg_50'].iloc[i]) * 100
        
        price_change = ((row['close'] - prev['close']) / prev['close']) * 100
        
        # 거래량 급증: 평균 대비 50%+ 증가
        if vol_pct >= 50:
            results['volume_surges'].append({
                'date': df.index[i],
                'volume_pct_above_avg': vol_pct,
                'price_change_pct': price_change,
                'signal': 'BREAKOUT BUY SIGNAL' if price_change > 0 
                         else 'DISTRIBUTION WARNING'
            })
        
        # 거래량 건조: 평균 대비 50% 이하
        if vol_pct <= -50:
            results['volume_dryups'].append({
                'date': df.index[i],
                'volume_pct_below_avg': abs(vol_pct),
                'note': 'Selling exhaustion — constructive near base lows'
            })
        
        # 분배일 (Distribution Day) — 시장 방향 판단 핵심
        # 인덱스가 0.2%+ 하락하면서 전일 대비 거래량 증가
        if (price_change < -0.2 and 
            row['volume'] > prev['volume']):
            results['distribution_days'].append({
                'date': df.index[i],
                'price_decline_pct': price_change,
                'volume_increase': True
            })
        
        # 축적일 (Accumulation Day)
        if (price_change > 0.2 and 
            row['volume'] > prev['volume'] and
            vol_pct > 0):
            results['accumulation_days'].append({
                'date': df.index[i],
                'price_gain_pct': price_change,
                'vol_pct_above_avg': vol_pct
            })
    
    return results
```

---

### 5. 매수/매도 포인트 자동 표시

```python
def mark_buy_sell_points(df, patterns, volume_analysis):
    """
    감지된 패턴과 거래량 분석을 기반으로 
    매수/매도 포인트를 자동 표시
    """
    signals = []
    
    for pattern in patterns:
        pivot = pattern['pivot_point']
        
        # 매수 포인트: 피벗 돌파 + 거래량 50%+ 증가
        for i, row in df.iterrows():
            if row['close'] > pivot:
                vol_pct = ((row['volume'] - df['vol_avg_50'].loc[i]) / 
                          df['vol_avg_50'].loc[i]) * 100
                
                if vol_pct >= 50:
                    signals.append({
                        'date': i,
                        'type': 'BUY',
                        'price': row['close'],
                        'pivot_point': pivot,
                        'pattern': pattern['type'],
                        'volume_pct_above_avg': vol_pct,
                        'note': f"Breakout from {pattern['type']} on "
                                f"{vol_pct:.0f}% above average volume"
                    })
                    break  # 첫 번째 유효한 돌파만 표시
        
        # 매수 후 최대 추격 가격 (피벗 +5%)
        max_chase = pivot * 1.05
        
        # 손절 가격 (매수가 -7~8%)
        if signals and signals[-1]['type'] == 'BUY':
            buy_price = signals[-1]['price']
            signals.append({
                'type': 'STOP_LOSS',
                'price': buy_price * 0.92,
                'note': "Cut loss at 7-8% below purchase price — NO EXCEPTIONS"
            })
            
            # 이익실현 가격 (매수가 +20~25%)
            signals.append({
                'type': 'PROFIT_TARGET',
                'price': buy_price * 1.20,
                'note': "Take profit at 20-25% gain (unless stock rockets "
                        "20%+ in under 3 weeks — then HOLD 8 weeks minimum)"
            })
    
    # 클라이맥스 탑 매도 신호 감지
    for surge in volume_analysis['volume_surges']:
        # 장기 상승 후 최대 일간 상승 + 최대 거래량 = 클라이맥스 탑
        pass  # 이전 시스템 프롬프트의 매도 규칙 10가지 구현
    
    return signals
```

---

### 6. 오닐 스타일 차트 생성 (시각화)

```python
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import FancyArrowPatch
import mplfinance as mpf

def create_oneil_chart(df, patterns, signals, ticker):
    """
    오닐의 책에 나오는 것과 유사한 어노테이션 차트 생성
    
    포함 요소:
    - 캔들스틱/바 차트
    - 10주(50일), 30주(150일), 40주(200일) 이동평균선
    - 거래량 바 차트 (평균 대비 색상 구분)
    - Base 영역 표시
    - Buy/Sell 포인트 화살표
    - 피벗 포인트 수평선
    - 패턴 이름 및 기간 레이블
    """
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 10),
                                     gridspec_kw={'height_ratios': [3, 1]},
                                     sharex=True)
    
    # --- 가격 차트 ---
    ax1.plot(df.index, df['close'], color='black', linewidth=1)
    ax1.plot(df.index, df['ma_10w'], color='red', linewidth=0.8, 
             label='10-week MA (50-day)')
    ax1.plot(df.index, df['ma_40w'], color='blue', linewidth=0.8,
             label='40-week MA (200-day)')
    
    # Base 영역 표시 (반투명 박스)
    for pattern in patterns:
        ax1.axhspan(pattern.get('cup_low', pattern.get('low', 0)),
                    pattern.get('left_peak', pattern.get('high', 0)),
                    xmin=0, xmax=1,
                    alpha=0.1, color='blue',
                    label=f"{pattern['type']} base")
        
        # 패턴 이름 레이블
        mid_date = pattern['start_date'] + (pattern['end_date'] - 
                                             pattern['start_date']) / 2
        ax1.annotate(
            f"{pattern['type'].replace('_', ' ').title()}\n"
            f"{pattern['duration_weeks']}w, "
            f"depth {pattern.get('depth_pct', pattern.get('correction_pct', 0)):.0f}%",
            xy=(mid_date, pattern.get('cup_low', pattern.get('low', 0))),
            fontsize=8, ha='center',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='lightyellow')
        )
        
        # 피벗 포인트 수평선
        ax1.axhline(y=pattern['pivot_point'], color='green', 
                    linestyle='--', linewidth=0.8, alpha=0.7)
        ax1.annotate(f"Pivot: {pattern['pivot_point']:.2f}",
                    xy=(df.index[-1], pattern['pivot_point']),
                    fontsize=8, color='green')
    
    # 매수/매도 신호 화살표
    for signal in signals:
        if signal['type'] == 'BUY':
            ax1.annotate('Buy', xy=(signal['date'], signal['price']),
                        xytext=(signal['date'], signal['price'] * 0.95),
                        arrowprops=dict(arrowstyle='->', color='green', lw=2),
                        fontsize=10, fontweight='bold', color='green')
        elif signal['type'] == 'STOP_LOSS':
            ax1.axhline(y=signal['price'], color='red', 
                        linestyle=':', linewidth=1)
            ax1.annotate(f"Stop Loss: {signal['price']:.2f} (-7%)",
                        xy=(df.index[-1], signal['price']),
                        fontsize=8, color='red')
    
    ax1.set_ylabel('Price')
    ax1.set_title(f'{ticker} — O\'Neil CAN SLIM Chart Analysis', fontsize=14)
    ax1.legend(loc='upper left', fontsize=8)
    ax1.set_yscale('log')  # 오닐은 로그 스케일 사용
    
    # --- 거래량 차트 ---
    colors = ['red' if df['close'].iloc[i] < df['close'].iloc[i-1] 
              else 'black' for i in range(1, len(df))]
    colors.insert(0, 'black')
    
    # 평균 이상 거래량은 더 진하게
    for i in range(len(df)):
        alpha = 1.0 if df['volume'].iloc[i] > df['vol_avg_50'].iloc[i] else 0.3
        ax2.bar(df.index[i], df['volume'].iloc[i], 
                color=colors[i], alpha=alpha, width=1)
    
    # 50일 거래량 평균선
    ax2.plot(df.index, df['vol_avg_50'], color='blue', 
             linewidth=0.8, label='50-day avg volume')
    
    # 거래량 급증 포인트 표시
    for surge in [s for s in signals 
                  if s.get('volume_pct_above_avg', 0) > 100]:
        ax2.annotate(f"Vol +{surge['volume_pct_above_avg']:.0f}%",
                    xy=(surge['date'], df.loc[surge['date'], 'volume']),
                    fontsize=7, color='blue', fontweight='bold')
    
    ax2.set_ylabel('Volume')
    ax2.legend(loc='upper left', fontsize=8)
    
    plt.tight_layout()
    return fig
```

---

### 7. Base Stage 카운팅 (단계 추적)

오닐은 1단계, 2단계, 3단계, 4단계 base를 구분합니다.
3~4단계는 실패 확률이 높습니다.

```python
def count_base_stages(patterns):
    """
    같은 종목의 연속 base 패턴을 추적하여 단계 부여
    1단계: 가장 강력
    2단계: 여전히 유효
    3~4단계: 위험 증가, 실패 가능성 높음
    """
    if not patterns:
        return patterns
    
    stage = 1
    for i, pattern in enumerate(patterns):
        pattern['stage'] = stage
        
        if i > 0:
            prev = patterns[i-1]
            # 새로운 base가 이전 base의 돌파 후 형성되었으면 단계 증가
            if pattern['start_date'] > prev['end_date']:
                stage += 1
                pattern['stage'] = stage
        
        # 오닐 경고 추가
        if stage >= 3:
            pattern['warning'] = (
                f"CAUTION: This is a Stage {stage} base. "
                "Late-stage bases have significantly higher failure rates. "
                "O'Neil warns that 3rd and 4th stage bases are increasingly "
                "risky and failure-prone."
            )
    
    return patterns
```

---

### 8. Faulty Pattern 감지 (불량 패턴 필터링)

오닐이 강조한 불량 패턴 특징들:

```python
def check_pattern_faults(pattern, df):
    """
    오닐이 경고한 불량 패턴 특징 체크
    Returns: list of faults found
    """
    faults = []
    
    # 1. Wide and Loose — 주간 가격 변동폭이 너무 큼
    weekly_ranges = df.loc[pattern['start_date']:pattern['end_date']]
    avg_range = ((weekly_ranges['high'] - weekly_ranges['low']) / 
                 weekly_ranges['close']).mean() * 100
    if avg_range > 15:
        faults.append("WIDE AND LOOSE: Weekly price spreads are too large. "
                      "O'Neil says these are failure-prone.")
    
    # 2. 핸들이 하단 1/2에 형성
    if pattern.get('handle_in_upper_half') is False:
        faults.append("HANDLE IN LOWER HALF: Handle formed below the "
                      "midpoint of the base. Demand has not been strong enough.")
    
    # 3. 웨지형 핸들 (상향 드리프트)
    # 핸들의 저점이 점점 올라가면 불량
    if pattern['type'] == 'cup_with_handle':
        # 핸들 저점 추세 확인
        handle_lows = df.loc[pattern.get('handle_start'):pattern['end_date']]['low']
        if len(handle_lows) >= 3:
            if all(handle_lows.iloc[i] >= handle_lows.iloc[i-1] 
                   for i in range(1, len(handle_lows))):
                faults.append("WEDGING HANDLE: Handle drifts upward along "
                            "its lows. O'Neil says this has much higher "
                            "probability of failing.")
    
    # 4. V자형 바닥 (U자형이 아닌)
    if pattern.get('u_shape') is False:
        faults.append("V-SHAPED BOTTOM: Stock came straight off the bottom "
                     "without time to shake out weak holders. Higher risk.")
    
    # 5. 3단계 이상 base
    if pattern.get('stage', 1) >= 3:
        faults.append(f"LATE-STAGE BASE (Stage {pattern['stage']}): "
                     "Higher failure rate. Most big moves come from "
                     "1st and 2nd stage bases.")
    
    # 6. 깊이 과다 (50% 이상)
    depth = pattern.get('depth_pct', 0)
    if depth > 50:
        faults.append(f"EXCESSIVE DEPTH ({depth:.0f}%): Corrections over "
                     "50% from peak have higher failure rate. Stock must "
                     "gain 100%+ just to return to prior high.")
    
    # 7. 상대강도 하락 추세
    # RS line이 base 형성 중 하락하면 불량
    
    return faults
```

---

## API 통합 아키텍처

### 전체 흐름

```
사용자: "삼성전자 차트 분석해줘"
         ↓
    [Function Calling]
         ↓
    주가 데이터 API 호출 (yfinance / 한국투자증권 API)
         ↓
    OHLCV 데이터 수신 (최소 1년, 이상 2~3년)
         ↓
    패턴 감지 엔진 실행
    ├── Cup-with-Handle 감지
    ├── Double Bottom 감지
    ├── Flat Base 감지
    ├── High Tight Flag 감지
    ├── 거래량 분석
    ├── Base Stage 카운팅
    └── Faulty Pattern 체크
         ↓
    차트 이미지 생성 (matplotlib)
    + 분석 결과 JSON
         ↓
    AI (오닐 페르소나)가 결과를 해석하여 응답
    "이 종목은 현재 26주간의 Cup-with-Handle 패턴 2단계를 형성 중입니다.
     깊이 18%, 핸들이 상단에서 적절히 형성되고 있으며..."
```

### Function Calling 정의 (예시)

```json
{
  "name": "analyze_stock_chart",
  "description": "Analyze a stock's price chart for O'Neil CAN SLIM patterns",
  "parameters": {
    "type": "object",
    "properties": {
      "ticker": {
        "type": "string",
        "description": "Stock ticker symbol (e.g., AAPL, 005930.KS)"
      },
      "period": {
        "type": "string",
        "description": "Data period (e.g., '2y' for 2 years)",
        "default": "2y"
      }
    },
    "required": ["ticker"]
  }
}
```

---

## 구현 우선순위

### Phase 1 (지금 ~ 2주)
1. ✅ 시스템 프롬프트 완성
2. yfinance로 미국 주식 데이터 가져오기
3. Cup-with-Handle 패턴 감지 구현
4. 기본 차트 시각화

### Phase 2 (2~4주)
5. Double Bottom, Flat Base 감지 추가
6. 거래량 분석 모듈
7. 매수/매도 포인트 자동 표시
8. Base Stage 카운팅

### Phase 3 (4~8주)
9. High Tight Flag, Ascending Base 감지
10. Faulty Pattern 필터링
11. 한국 주식 API 연동
12. Function Calling으로 AI 통합

### Phase 4 (선택)
13. 멀티모달 AI로 차트 이미지 직접 분석 (보조)
14. 실시간 알림 시스템
15. 백테스팅 모듈

---

## 중요 주의사항

1. **완벽한 자동 감지는 불가능** — 오닐 자신도 수십 년 경험으로 패턴을 판단. AI는 후보를 감지하고, 최종 판단은 사용자에게 맡겨야 함
2. **과적합 방지** — 너무 엄격한 규칙은 좋은 패턴도 놓치고, 너무 느슨하면 불량 패턴을 잡음. 오닐의 수치 기준을 기본값으로 사용하되, quality score로 순위화
3. **시장 방향(M 팩터) 필수** — 아무리 좋은 패턴이라도 약세장에서는 무효. 반드시 시장 지수의 분배일 카운팅과 함께 판단해야 함
4. **면책 조항** — 투자 추천이 아닌 교육 및 분석 도구임을 항상 명시
