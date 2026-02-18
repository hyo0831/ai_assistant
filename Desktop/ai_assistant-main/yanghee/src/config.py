import os
import sys
from dotenv import load_dotenv
load_dotenv()

# 언어 설정 (Language setting): "ko" = 한국어, "en" = English
LANGUAGE = "ko"

# OpenAI API Key (환경변수에서 로드)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY or OPENAI_API_KEY == "YOUR_API_KEY_HERE":
    print("[WARNING] OPENAI_API_KEY가 설정되지 않았습니다.")
    print("  API 키 발급: https://platform.openai.com/account/api-keys")
    print("  설정 방법: .env 파일에 OPENAI_API_KEY=your_key 추가")

# 분석 결과 저장 경로
RESULTS_DIR = "results"
os.makedirs(RESULTS_DIR, exist_ok=True)
