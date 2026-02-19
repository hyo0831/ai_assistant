"""
CAN SLIM Fundamental Analysis — 통합 오케스트레이터

각 요소별 데이터를 수집하고, AI가 판단할 수 있도록 근거 텍스트를 생성.
점수 산출은 하지 않음 — AI가 O'Neil 규칙 원문(RAG)을 참고하여 직접 판단.
"""

import yfinance as yf
from typing import Dict

from analysis.canslim import c_current_earnings
from analysis.canslim import a_annual_earnings
from analysis.canslim import n_new_catalyst
from analysis.canslim import s_supply_demand
from analysis.canslim import l_leader_laggard
from analysis.canslim import i_institutional
from analysis.canslim import m_market_direction
from analysis.utils import get_currency_info


def run_analysis(ticker: str) -> Dict:
    """
    CAN SLIM 전체 펀더멘털 데이터 수집

    Args:
        ticker: 종목 코드

    Returns:
        각 요소별 데이터 + AI 프롬프트용 통합 텍스트
    """
    print(f"\n[*] {ticker} 펀더멘털 데이터 수집 중...")

    result = {
        'ticker': ticker,
        'currency': 'USD',
        'company_name': '',
        'data': {},
        'prompt_text': '',
        'error': None
    }

    # 종목 유효성 검증
    try:
        stock = yf.Ticker(ticker)
        info = stock.info or {}
    except Exception as e:
        result['error'] = f'종목 데이터 로드 실패: {e}'
        print(f"[ERROR] {result['error']}")
        return result

    # 종목명이 없거나 비어있으면 잘못된 티커
    name = info.get('longName') or info.get('shortName') or ''
    if not name and not info.get('marketCap'):
        result['error'] = f"'{ticker}' 종목을 찾을 수 없습니다. 티커 심볼을 확인하세요."
        print(f"[ERROR] {result['error']}")
        return result

    result['company_name'] = name

    # 통화 감지
    currency_info = get_currency_info(ticker, info)
    currency = currency_info['code']
    result['currency'] = currency
    print(f"  종목명: {name} | 통화: {currency}")

    # 각 팩터별 데이터 수집 (에러 격리)
    factors = [
        ('C', '분기 실적', lambda: c_current_earnings.analyze(stock, info)),
        ('A', '연간 실적', lambda: a_annual_earnings.analyze(stock, info)),
        ('N', '신촉매', lambda: n_new_catalyst.analyze(stock, info)),
        ('S', '수급', lambda: s_supply_demand.analyze(stock, info)),
        ('L', '리더/래거드 + RS Rating', lambda: l_leader_laggard.analyze(stock, info, ticker)),
        ('I', '기관 보유', lambda: i_institutional.analyze(stock, info, ticker)),
        ('M', '시장 방향', lambda: m_market_direction.analyze(ticker)),
    ]

    for factor_key, factor_name, analyze_fn in factors:
        print(f"  [{factor_key}] {factor_name} 데이터 수집...")
        try:
            result['data'][factor_key] = analyze_fn()
        except Exception as e:
            print(f"  [WARN] {factor_key} 팩터 수집 실패: {e}")
            result['data'][factor_key] = {'data_note': f'수집 실패: {e}'}

    # 통합 프롬프트 텍스트 생성
    result['prompt_text'] = _build_prompt_text(ticker, result['data'], currency)

    print(f"[OK] {ticker} 펀더멘털 데이터 수집 완료!\n")
    return result


def _build_prompt_text(ticker: str, data: dict, currency: str = 'USD') -> str:
    """각 요소별 format_for_prompt를 호출하여 통합 텍스트 생성"""
    sections = []
    sections.append("=" * 60)
    sections.append(f"CAN SLIM FUNDAMENTAL DATA: {ticker}")
    sections.append("=" * 60)
    sections.append("")
    sections.append("Below is factual data collected for each CAN SLIM factor.")
    sections.append("Each section includes O'Neil's original rules for your reference.")
    sections.append("Evaluate each factor against O'Neil's criteria and provide your assessment.")
    sections.append("")

    # currency 파라미터를 지원하는 모듈들
    format_map = {
        'C': lambda d: c_current_earnings.format_for_prompt(d, currency=currency),
        'A': lambda d: a_annual_earnings.format_for_prompt(d, currency=currency),
        'N': lambda d: n_new_catalyst.format_for_prompt(d, currency=currency),
        'S': lambda d: s_supply_demand.format_for_prompt(d, currency=currency),
        'L': lambda d: l_leader_laggard.format_for_prompt(d),
        'I': lambda d: i_institutional.format_for_prompt(d),
        'M': lambda d: m_market_direction.format_for_prompt(d),
    }

    for key in ['C', 'A', 'N', 'S', 'L', 'I', 'M']:
        if key in data:
            try:
                sections.append(format_map[key](data[key]))
                sections.append("")
            except Exception as e:
                sections.append(f"### {key} - Data formatting error: {e}")
                sections.append("")

    sections.append("=" * 60)

    return "\n".join(sections)
