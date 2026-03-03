"""
CAN SLIM Fundamental Analysis - 통합 모듈

각 요소별 데이터를 수집하고, AI가 판단할 수 있도록 근거 텍스트를 생성.
점수 산출은 하지 않음 - AI가 O'Neil 규칙 원문(RAG)을 참고하여 직접 판단.

구조:
  canslim/c_current_earnings.py  - C: 분기 실적
  canslim/a_annual_earnings.py   - A: 연간 실적
  canslim/n_new_catalyst.py      - N: 신제품/촉매 (AI 조사)
  canslim/s_supply_demand.py     - S: 수급
  canslim/l_leader_laggard.py    - L: 리더/래거드 (RS Rating)
  canslim/i_institutional.py     - I: 기관 보유
  canslim/m_market_direction.py  - M: 시장 방향
"""

import yfinance as yf
from typing import Dict

from canslim import c_current_earnings
from canslim import a_annual_earnings
from canslim import n_new_catalyst
from canslim import s_supply_demand
from canslim import l_leader_laggard
from canslim import i_institutional
from canslim import m_market_direction


def analyze_fundamentals(ticker: str, rs_analysis: dict = None) -> Dict:
    """
    CAN SLIM 전체 펀더멘털 데이터 수집

    Args:
        ticker: 종목 코드
        rs_analysis: pattern_detector의 RS 분석 결과 (L 요소에 사용)

    Returns:
        각 요소별 데이터 + AI 프롬프트용 통합 텍스트
    """
    print(f"[*] Fetching fundamental data for {ticker}...")

    result = {
        'ticker': ticker,
        'data': {},       # 각 요소별 원본 데이터
        'prompt_text': '',  # AI 프롬프트에 삽입할 통합 텍스트
        'error': None
    }

    try:
        stock = yf.Ticker(ticker)
        info = stock.info or {}

        # C - Current Quarterly Earnings
        print("  [C] Collecting quarterly earnings data...")
        c_data = c_current_earnings.analyze(stock, info)
        result['data']['C'] = c_data

        # A - Annual Earnings
        print("  [A] Collecting annual earnings data...")
        a_data = a_annual_earnings.analyze(stock, info)
        result['data']['A'] = a_data

        # N - New Catalyst (AI 조사 포함)
        print("  [N] Analyzing new catalysts...")
        n_data = n_new_catalyst.analyze(stock, info)
        result['data']['N'] = n_data

        # S - Supply & Demand
        print("  [S] Collecting supply/demand data...")
        s_data = s_supply_demand.analyze(stock, info)
        result['data']['S'] = s_data

        # L - Leader or Laggard
        print("  [L] Evaluating leader/laggard status...")
        l_data = l_leader_laggard.analyze(info, rs_analysis)
        result['data']['L'] = l_data

        # I - Institutional Sponsorship
        print("  [I] Collecting institutional data...")
        i_data = i_institutional.analyze(stock, info)
        result['data']['I'] = i_data

        # M - Market Direction
        print("  [M] Analyzing market direction...")
        m_data = m_market_direction.analyze()
        result['data']['M'] = m_data

        # 통합 프롬프트 텍스트 생성
        result['prompt_text'] = _build_prompt_text(ticker, result['data'])

        print(f"[OK] Fundamental data collection complete for {ticker}")

    except Exception as e:
        result['error'] = str(e)
        result['prompt_text'] = f"Fundamental data collection error: {e}"
        print(f"[WARNING] Fundamental analysis error: {e}")

    return result


def _build_prompt_text(ticker: str, data: dict) -> str:
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

    # 각 요소별 텍스트
    if 'C' in data:
        sections.append(c_current_earnings.format_for_prompt(data['C']))
        sections.append("")

    if 'A' in data:
        sections.append(a_annual_earnings.format_for_prompt(data['A']))
        sections.append("")

    if 'N' in data:
        sections.append(n_new_catalyst.format_for_prompt(data['N']))
        sections.append("")

    if 'S' in data:
        sections.append(s_supply_demand.format_for_prompt(data['S']))
        sections.append("")

    if 'L' in data:
        sections.append(l_leader_laggard.format_for_prompt(data['L']))
        sections.append("")

    if 'I' in data:
        sections.append(i_institutional.format_for_prompt(data['I']))
        sections.append("")

    if 'M' in data:
        sections.append(m_market_direction.format_for_prompt(data['M']))
        sections.append("")

    sections.append("=" * 60)

    return "\n".join(sections)
