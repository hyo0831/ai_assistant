"""
Quick Test Script - API 키 및 라이브러리 동작 확인용
실제 분석 전에 이 스크립트를 먼저 실행하여 설정을 확인하세요.
"""

import os

def check_imports():
    """필수 라이브러리 import 체크"""
    print("[*] Checking required libraries...")

    required_libs = {
        'yfinance': 'yfinance',
        'mplfinance': 'mplfinance',
        'google.generativeai': 'google-generativeai',
        'pandas': 'pandas',
        'PIL': 'pillow'
    }

    missing = []

    for module, package in required_libs.items():
        try:
            __import__(module)
            print(f"  [OK] {package}")
        except ImportError:
            print(f"  [FAIL] {package} - NOT INSTALLED")
            missing.append(package)

    if missing:
        print(f"\n[!] Missing libraries: {', '.join(missing)}")
        print(f"Install with: pip install {' '.join(missing)}")
        return False

    print("\n[OK] All libraries installed!")
    return True


def check_api_key():
    """Gemini API 키 확인"""
    print("\n[*] Checking Gemini API Key...")

    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        print("  [FAIL] GEMINI_API_KEY not found in environment variables")
        print("\n[!] Set your API key:")
        print("  Windows (PowerShell): $env:GEMINI_API_KEY='your-key'")
        print("  Windows (CMD): set GEMINI_API_KEY=your-key")
        print("  Mac/Linux: export GEMINI_API_KEY='your-key'")
        print("\n  Or edit main.py line 17 directly")
        return False

    if api_key == "YOUR_API_KEY_HERE":
        print("  [!] API key is still set to placeholder value")
        print("  Please set your actual API key")
        return False

    print(f"  [OK] API Key found: {api_key[:10]}...{api_key[-4:]}")
    return True


def test_yfinance():
    """yfinance 간단 테스트"""
    print("\n[*] Testing yfinance connection...")

    try:
        import yfinance as yf

        # 간단한 데이터 다운로드 테스트
        ticker = yf.Ticker("AAPL")
        info = ticker.info

        print(f"  [OK] Successfully fetched data for AAPL")
        print(f"  Company: {info.get('longName', 'N/A')}")
        print(f"  Current Price: ${info.get('currentPrice', 'N/A')}")
        return True

    except Exception as e:
        print(f"  [FAIL] Error: {e}")
        return False


def test_gemini_api():
    """Gemini API 연결 테스트"""
    print("\n[*] Testing Gemini API connection...")

    try:
        import google.generativeai as genai

        api_key = os.environ.get("GEMINI_API_KEY")

        if not api_key:
            print("  [SKIP] Skipping (API key not set)")
            return False

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')

        # 간단한 테스트 요청
        response = model.generate_content("Say 'API connection successful' in one line.")

        print(f"  [OK] API connection successful!")
        print(f"  Response: {response.text[:100]}")
        return True

    except Exception as e:
        print(f"  [FAIL] Error: {e}")
        print(f"  Check your API key at: https://aistudio.google.com/app/apikey")
        return False


def main():
    """메인 테스트 실행"""
    print("=" * 70)
    print("WILLIAM O'NEIL AI ASSISTANT - QUICK TEST")
    print("=" * 70)
    print()

    results = []

    # 1. 라이브러리 체크
    results.append(("Libraries", check_imports()))

    # 2. API 키 체크
    results.append(("API Key", check_api_key()))

    # 3. yfinance 테스트
    results.append(("yfinance", test_yfinance()))

    # 4. Gemini API 테스트
    results.append(("Gemini API", test_gemini_api()))

    # 결과 요약
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    for name, success in results:
        status = "[PASS]" if success else "[FAIL]"
        print(f"  {name:<15} {status}")

    print("=" * 70)

    all_passed = all(result[1] for result in results)

    if all_passed:
        print("\n[SUCCESS] All tests passed! You're ready to run main.py")
        print("   Run: python main.py")
    else:
        print("\n[WARNING] Some tests failed. Please fix the issues above before running main.py")

    print()


if __name__ == "__main__":
    main()
