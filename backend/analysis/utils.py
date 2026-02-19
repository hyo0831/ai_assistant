"""
통화 감지, 금액 포맷, 시장 판별 유틸리티
"""


def is_korean_stock(ticker: str) -> bool:
    t = ticker.upper()
    return t.endswith('.KS') or t.endswith('.KQ')


def is_japanese_stock(ticker: str) -> bool:
    return ticker.upper().endswith('.T')


def get_currency_info(ticker: str, info: dict) -> dict:
    """종목의 통화 정보 반환"""
    currency = info.get('currency', 'USD')
    if is_korean_stock(ticker):
        currency = 'KRW'
    elif is_japanese_stock(ticker):
        currency = 'JPY'

    symbols = {'USD': '$', 'KRW': '₩', 'JPY': '¥', 'EUR': '€', 'GBP': '£'}
    return {
        'code': currency,
        'symbol': symbols.get(currency, currency + ' '),
    }


def format_price(value, currency_code: str = 'USD') -> str:
    """가격 포맷 (통화별)"""
    if value is None:
        return 'N/A'
    symbols = {'USD': '$', 'KRW': '₩', 'JPY': '¥', 'EUR': '€', 'GBP': '£'}
    sym = symbols.get(currency_code, currency_code + ' ')

    if currency_code == 'KRW':
        return f"{sym}{int(value):,}"
    elif currency_code == 'JPY':
        return f"{sym}{int(value):,}"
    else:
        return f"{sym}{value:,.2f}"


def format_large_number(value, currency_code: str = 'USD') -> str:
    """큰 숫자를 읽기 쉽게 포맷 (통화별 단위)"""
    if value is None:
        return 'N/A'
    symbols = {'USD': '$', 'KRW': '₩', 'JPY': '¥', 'EUR': '€', 'GBP': '£'}
    sym = symbols.get(currency_code, '')
    abs_val = abs(value)
    sign = '-' if value < 0 else ''

    if currency_code == 'KRW':
        if abs_val >= 1e12:
            return f"{sign}{sym}{abs_val/1e12:.1f}조"
        elif abs_val >= 1e8:
            return f"{sign}{sym}{abs_val/1e8:.0f}억"
        elif abs_val >= 1e4:
            return f"{sign}{sym}{abs_val/1e4:.0f}만"
        else:
            return f"{sign}{sym}{int(abs_val):,}"
    elif currency_code == 'JPY':
        if abs_val >= 1e12:
            return f"{sign}{sym}{abs_val/1e12:.1f}兆"
        elif abs_val >= 1e8:
            return f"{sign}{sym}{abs_val/1e8:.0f}億"
        else:
            return f"{sign}{sym}{int(abs_val):,}"
    else:
        if abs_val >= 1e12:
            return f"{sign}{sym}{abs_val/1e12:.1f}T"
        elif abs_val >= 1e9:
            return f"{sign}{sym}{abs_val/1e9:.1f}B"
        elif abs_val >= 1e6:
            return f"{sign}{sym}{abs_val/1e6:.0f}M"
        else:
            return f"{sign}{sym}{abs_val:,.0f}"


def get_market_cap_label(mcap, currency_code: str = 'USD') -> str:
    """시가총액 규모 분류 (통화별 기준)"""
    if mcap is None:
        return ''
    if currency_code == 'KRW':
        # 한국 기준: 대형 10조+, 중형 2조+, 소형 미만
        if mcap >= 10e12:
            return 'Large Cap'
        elif mcap >= 2e12:
            return 'Mid Cap'
        else:
            return 'Small Cap'
    elif currency_code == 'JPY':
        if mcap >= 1e12:
            return 'Large Cap'
        elif mcap >= 200e9:
            return 'Mid Cap'
        else:
            return 'Small Cap'
    else:
        # USD 기준
        if mcap >= 10e9:
            return 'Large Cap'
        elif mcap >= 2e9:
            return 'Mid Cap'
        else:
            return 'Small Cap'


def find_financial_row(df, preferred_names: list):
    """재무제표에서 여러 이름으로 행을 찾아 반환"""
    if df is None or df.empty:
        return None
    for name in preferred_names:
        if name in df.index:
            series = df.loc[name].dropna()
            if not series.empty:
                return series
    return None


# Net Income 찾기용 이름 목록
NET_INCOME_NAMES = [
    'Net Income',
    'Net Income Common Stockholders',
    'Net Income Including Noncontrolling Interests',
    'Net Income From Continuing Operations',
]

REVENUE_NAMES = [
    'Total Revenue',
    'Operating Revenue',
    'Revenue',
]

SHARE_COUNT_NAMES = [
    'Ordinary Shares Number',
    'Share Issued',
    'Common Stock',
    'Common Stock Shares Outstanding',
]
