"""
M - Market Direction

O'Neil: "투자의 50%는 시장 방향"
S&P 500, NASDAQ + 한국 KOSPI/KOSDAQ 지수의 추세 및 Distribution Day 데이터 수집.
"""

import pandas as pd
import yfinance as yf
from typing import Dict
from analysis.utils import is_korean_stock

ONEIL_RULE = """
### M — Market Direction (O'Neil 원문 규칙)

[왜 가장 중요한가]
- CAN SLIM의 C·A·N·S·L·I를 다 맞춰도 시장 방향이 하락이면 보유 주식의 3/4이 함께 떨어진다
- "시장 타이밍은 불가능하다"는 말은 월가·미디어의 신화 — 실제로 방법이 있다
- 개인 투자자는 5~20종목만 보유 → 기관보다 현금 비중 조절이 더 유리하고 중요함
- 뉴스레터·애널리스트 의견·경제지표는 불필요 — 지수 차트를 직접 관찰할 것

[시장 고점 파악 — Distribution Day]
- Distribution Day: 전날보다 거래량이 증가했는데 지수가 0.2%+ 하락한 날
- Stalling Day: 거래량이 늘었는데도 상승폭이 미미한 날 (숨겨진 매도 압력)
- 4~5주 안에 Distribution Day가 4~5회 나타나면 거의 항상 하락세로 전환
- 주의: 분산은 시장이 아직 오르는 도중에 발생 — 많은 사람이 알아채지 못함
- 약세장 특징: 강하게 시작해 약하게 마감 / 강세장: 약하게 시작해 강하게 마감

[랠리 실패 신호 3가지 (고점 이후)]
1. 랠리 3~5일째에 거래량이 줄면서 지수가 오를 때
2. 전날 대비 상승폭이 미미할 때
3. 첫 하락분의 절반도 회복하지 못할 때

[시장 고점의 추가 신호들]
- 선도주들이 3~4번째 베이스에서 돌파할 때 (넓고 느슨한 패턴)
- 클라이맥스 탑(Climax Top): 선도주가 몇 달 상승 후 2~3주 만에 급등
- 저가·저품질 라거드 주식들이 강세를 보일 때 — "칠면조도 강풍에는 날 수 있다"
- 최근 4~5개 신규 매수 종목에서 수익이 전혀 나지 않을 때

[시장 저점 파악 — Follow-Through Day]
- 하락 중 랠리 시도 발생 → 바로 따라붙지 말고 기다릴 것
- 랠리 시도 4~7일째에 주요 지수가 전날보다 높은 거래량과 함께 강하게 상승
- 이 신호 없이 시작된 새 강세장은 역사상 한 번도 없었음
- Follow-Through 확인 후에도 즉시 전부 매수 금지 — 건실한 패턴 돌파 종목부터 조금씩

[약세장 주의 사항]
- 전형적인 약세장은 3단계 하락 — 중간에 그럴듯한 가짜 랠리가 있어 투자자를 끌어들임
- "바닥 낚시(Bottom Fishing)" 위험: 기관 반등 유인 후 추가 하락 패턴
- 약세장은 보통 5~6개월 이상, 심각할 경우 2년까지 지속
- 손실 33% → 회복에 +50% 필요 / 손실 50% → 회복에 +100% 필요

[연준 금리 참고]
- 기준금리 연속 3회 인상 → 약세장·경기침체 시작 신호인 경우 많음
- 단, 주가 지수 자체가 금리보다 더 앞선 바로미터 — 금리만 보다가는 늦을 수 있음
- 금리 인하 후에도 시장이 계속 하락하는 경우 있음 (2000~2001년 실제 사례)

[보조 지표 주의사항 (신뢰도 낮음)]
- 풋/콜 비율, A-D Line, 나스닥/NYSE 거래량 비율 등은 보조 참고용
- 새 강세장 초반에 "과매수" 상태가 되어도 매도 신호 아님 — 맹신 위험
- 이 모든 보조 지표는 주요 지수 직접 관찰만큼 신뢰할 수 없음
- 전문가 의견·CNBC 추천보다 지수 차트가 항상 우선
""".strip()


def analyze(ticker: str = '') -> Dict:
    """시장 방향 데이터 수집"""
    result = {
        'sp500': _analyze_index('^GSPC', 'S&P 500'),
        'nasdaq': _analyze_index('^IXIC', 'NASDAQ'),
        'data_note': ''
    }

    # 한국 주식이면 KOSPI/KOSDAQ도 분석
    if is_korean_stock(ticker):
        result['kospi'] = _analyze_index('^KS11', 'KOSPI')
        result['kosdaq'] = _analyze_index('^KQ11', 'KOSDAQ')

    return result


def _analyze_index(ticker: str, name: str) -> Dict:
    """개별 지수 분석 데이터"""
    data = {
        'name': name,
        'current_price': None,
        'vs_52wk_high': None,           # 52주 고점 대비 %
        'price_change_5d': None,         # 최근 5거래일 수익률
        'vs_50dma': None,                # 50일 이동평균 대비 %
        'vs_200dma': None,               # 200일 이동평균 대비 %
        'trend': 'N/A',
        'distribution_days_5wk': 0,      # 최근 5주 Distribution Day 수
        'stalling_days_5wk': 0,          # 최근 5주 Stalling Day 수
        'recent_distribution': [],        # 최근 Distribution Day 상세
    }

    try:
        idx = yf.Ticker(ticker)
        df = idx.history(period="1y", interval="1d")  # 1y로 통합 (52wk + 200dma 모두 커버)

        if df is None or df.empty or len(df) < 20:
            return data

        closes = df['Close'].values
        volumes = df['Volume'].values
        highs = df['High'].values
        dates = df.index
        current = closes[-1]
        data['current_price'] = round(float(current), 2)

        # 52주 고점 대비
        high_52wk = float(max(highs))
        if high_52wk > 0:
            data['vs_52wk_high'] = round(((current - high_52wk) / high_52wk) * 100, 1)

        # 최근 5거래일 수익률
        if len(closes) >= 6:
            data['price_change_5d'] = round(((closes[-1] - closes[-6]) / closes[-6]) * 100, 1)

        # 이동평균 대비
        if len(closes) >= 50:
            ma50 = pd.Series(closes).rolling(50).mean().iloc[-1]
            if not pd.isna(ma50) and ma50 > 0:
                data['vs_50dma'] = round(((current - ma50) / ma50) * 100, 1)

        if len(closes) >= 200:
            ma200 = pd.Series(closes).rolling(200).mean().iloc[-1]
            if not pd.isna(ma200) and ma200 > 0:
                data['vs_200dma'] = round(((current - ma200) / ma200) * 100, 1)

        # 추세 판단 (50dma + 200dma 조합)
        v50 = data['vs_50dma']
        v200 = data['vs_200dma']
        if v50 is not None and v200 is not None:
            if v50 > 2 and v200 > 0:
                data['trend'] = 'CONFIRMED UPTREND'
            elif v50 > 2:
                data['trend'] = 'UPTREND'
            elif v50 < -2 and v200 < 0:
                data['trend'] = 'CONFIRMED DOWNTREND'
            elif v50 < -2:
                data['trend'] = 'DOWNTREND'
            else:
                data['trend'] = 'SIDEWAYS'
        elif v50 is not None:
            if v50 > 2:
                data['trend'] = 'UPTREND'
            elif v50 < -2:
                data['trend'] = 'DOWNTREND'
            else:
                data['trend'] = 'SIDEWAYS'

        # Distribution Day + Stalling Day 카운트 (최근 25거래일 ≈ 5주)
        dist_count = 0
        stall_count = 0
        lookback = min(25, len(df) - 1)
        for i in range(len(df) - lookback, len(df)):
            if i < 1:
                continue
            daily_change = (closes[i] - closes[i-1]) / closes[i-1]
            vol_higher = volumes[i] > volumes[i-1]

            if daily_change <= -0.002 and vol_higher:
                # Distribution Day: 거래량 증가 + 0.2%+ 하락
                dist_count += 1
                date_str = dates[i].strftime('%Y-%m-%d') if hasattr(dates[i], 'strftime') else str(dates[i])
                data['recent_distribution'].append({
                    'date': date_str,
                    'change': round(float(daily_change * 100), 2)
                })
            elif 0 <= daily_change < 0.002 and vol_higher:
                # Stalling Day: 거래량 증가했으나 상승 미미 (0~0.2% 미만)
                stall_count += 1

        data['distribution_days_5wk'] = dist_count
        data['stalling_days_5wk'] = stall_count

    except Exception:
        pass

    return data


def format_for_prompt(data: Dict) -> str:
    """AI 프롬프트에 삽입할 텍스트 생성"""
    lines = ["### M - Market Direction"]

    # 모든 지수 키를 순회 (sp500, nasdaq + 한국 kospi, kosdaq)
    index_keys = ['sp500', 'nasdaq', 'kospi', 'kosdaq']
    for key in index_keys:
        if key not in data:
            continue
        idx = data[key]
        name = idx.get('name', key)
        lines.append(f"\n**{name}:**")

        if idx.get('current_price'):
            lines.append(f"  현재가: {idx['current_price']:,.2f}")

        if idx.get('price_change_5d') is not None:
            c5 = idx['price_change_5d']
            lines.append(f"  최근 5거래일: {c5:+.1f}%")

        if idx.get('vs_52wk_high') is not None:
            v52 = idx['vs_52wk_high']
            if v52 >= -5:
                lines.append(f"  vs 52주 고점: {v52:+.1f}% (고점 근처)")
            elif v52 >= -15:
                lines.append(f"  vs 52주 고점: {v52:+.1f}% (고점 대비 조정 중)")
            elif v52 >= -20:
                lines.append(f"  vs 52주 고점: {v52:+.1f}% (조정 심화 — 약세장 진입 경계)")
            else:
                lines.append(f"  vs 52주 고점: {v52:+.1f}% (고점에서 크게 이탈 — 약세장 가능성 높음)")

        if idx.get('vs_50dma') is not None:
            v = idx['vs_50dma']
            flag = "(상방 — 강세)" if v > 0 else "(하방 — 주의)"
            lines.append(f"  vs 50-DMA: {v:+.1f}% {flag}")

        if idx.get('vs_200dma') is not None:
            v = idx['vs_200dma']
            flag = "(상방)" if v > 0 else "(하방 — 약세장 영역)"
            lines.append(f"  vs 200-DMA: {v:+.1f}% {flag}")

        trend = idx.get('trend', 'N/A')
        if trend != 'N/A':
            trend_desc = {
                'CONFIRMED UPTREND': '확인된 상승추세 (50MA + 200MA 모두 상방)',
                'UPTREND': '상승추세 (50MA 상방)',
                'SIDEWAYS': '횡보 (50MA 근처)',
                'DOWNTREND': '하락추세 (50MA 하방)',
                'CONFIRMED DOWNTREND': '확인된 하락추세 (50MA + 200MA 모두 하방 — 위험)',
            }.get(trend, trend)
            lines.append(f"  추세: {trend_desc}")

        dist_count = idx.get('distribution_days_5wk', 0)
        stall_count = idx.get('stalling_days_5wk', 0)

        if dist_count >= 5:
            lines.append(f"  Distribution Days (5주): {dist_count}개 — 시장 고점 신호 (매우 위험, 즉시 포지션 축소)")
        elif dist_count >= 4:
            lines.append(f"  Distribution Days (5주): {dist_count}개 — O'Neil 경고 임계치 (강력 주의)")
        elif dist_count >= 3:
            lines.append(f"  Distribution Days (5주): {dist_count}개 — 누적 주의 구간 (신규 매수 자제)")
        else:
            lines.append(f"  Distribution Days (5주): {dist_count}개 — 정상 범위")

        if stall_count > 0:
            lines.append(f"  Stalling Days (5주): {stall_count}개 — 거래량 증가 대비 상승 미미 (숨겨진 매도 압력)")

        dist_list = idx.get('recent_distribution', [])
        if dist_list:
            lines.append(f"  최근 Distribution Days (오래된→최근):")
            for d in dist_list[-5:]:
                lines.append(f"    {d['date']}: {d['change']:+.2f}%")

    # 종합 시장 상태 판단
    lines.append("\n[종합 시장 상태]")
    max_dist = 0
    any_confirmed_down = False
    all_down = True
    checked_keys = [k for k in index_keys if k in data]

    for key in checked_keys:
        idx_data = data[key]
        max_dist = max(max_dist, idx_data.get('distribution_days_5wk', 0))
        trend = idx_data.get('trend', 'N/A')
        if trend == 'CONFIRMED DOWNTREND':
            any_confirmed_down = True
        if trend not in ('DOWNTREND', 'CONFIRMED DOWNTREND'):
            all_down = False

    if any_confirmed_down or (all_down and len(checked_keys) > 0):
        lines.append("  CONFIRMED DOWNTREND: 신규 매수 중단, 현금 비중 확대 강력 권고")

    if max_dist >= 5:
        lines.append(f"  Distribution {max_dist}개 — 시장 고점 신호 강함 (O'Neil: 4~5주 내 4~5개면 거의 항상 하락 전환)")
    elif max_dist >= 4:
        lines.append(f"  Distribution {max_dist}개 — 경고 임계치 근접, 포지션 축소 고려")
    elif max_dist >= 3:
        lines.append(f"  Distribution {max_dist}개 — 주의 구간")
    else:
        lines.append(f"  Distribution {max_dist}개 — 현재 이상 신호 없음")

    lines.append("")
    lines.append("[AI 판단 요청 사항]")
    lines.append("- 추세 + Distribution Day 수를 종합해 현재 시장 국면 판단 (강세/횡보/약세/고점 경고)")
    lines.append("- Distribution 4개+ 시: 포지션 축소 및 현금 비중 확대 권고 여부 판단")
    lines.append("- 50DMA 하방 + 200DMA 하방 동시: 약세장 진입 경고 여부 판단")
    lines.append("- 52주 고점 대비 -20% 초과: 약세장(Bear Market) 공식 진입 여부 판단")
    lines.append("- Stalling Day 존재 시 숨겨진 매도 압력으로 추가 주의 요청")
    lines.append("- 개인 투자자 관점 (5~20종목 보유 가정): 현금 비중 조절 권고 수준 언급")
    lines.append("- 현재 시장 국면이 Follow-Through Day 대기 중인지, 또는 랠리 실패 신호 여부 판단")

    if data.get('data_note'):
        lines.append(f"\nNote: {data['data_note']}")

    lines.append("")
    lines.append(ONEIL_RULE)

    return "\n".join(lines)
