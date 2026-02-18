import os
from dotenv import load_dotenv
load_dotenv()

# 언어 설정 (Language setting): "ko" = 한국어, "en" = English
LANGUAGE = "ko"

# Gemini API Key (환경변수에서 로드)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_API_KEY_HERE":
    print("[WARNING] GEMINI_API_KEY가 설정되지 않았습니다.")
    print("  API 키 발급: https://aistudio.google.com/app/apikey")
    print("  설정 방법: export GEMINI_API_KEY='your-key-here'")

# 차트 저장 경로
CHART_OUTPUT_PATH = "results/chart.png"

# 분석 결과 저장 경로
RESULTS_DIR = "results"
os.makedirs(RESULTS_DIR, exist_ok=True)
