#!/bin/bash

# William O'Neil AI Investment Assistant - Mac Setup Script
# This script helps you set up the environment on macOS

echo "===================================="
echo "Mac 환경 설정 스크립트"
echo "===================================="
echo ""

# 1. Python 버전 확인
echo "[1/5] Python 버전 확인 중..."
python3 --version
if [ $? -ne 0 ]; then
    echo "❌ Python3가 설치되지 않았습니다."
    echo "   Homebrew로 설치: brew install python3"
    exit 1
fi
echo "✅ Python3 설치 확인 완료"
echo ""

# 2. 가상환경 활성화
echo "[2/5] 가상환경 활성화 중..."
if [ ! -d "venv" ]; then
    echo "❌ 가상환경이 없습니다. 먼저 python3 -m venv venv를 실행하세요."
    exit 1
fi
source venv/bin/activate
echo "✅ 가상환경 활성화 완료"
echo ""

# 3. 환경 변수 설정 확인
echo "[3/5] 환경 변수 확인 중..."
if [ -z "$GEMINI_API_KEY" ]; then
    echo "⚠️  GEMINI_API_KEY가 설정되지 않았습니다."
    echo ""
    echo "API 키 설정 방법:"
    echo "1. Google AI Studio에서 API 키 생성: https://aistudio.google.com/app/apikey"
    echo "2. 아래 명령어로 환경 변수 설정:"
    echo "   export GEMINI_API_KEY='your-api-key-here'"
    echo ""
    echo "영구적으로 설정하려면 ~/.zshrc 또는 ~/.bash_profile에 추가하세요:"
    echo "   echo 'export GEMINI_API_KEY=\"your-api-key-here\"' >> ~/.zshrc"
    echo "   source ~/.zshrc"
    echo ""
else
    echo "✅ GEMINI_API_KEY 설정 확인 완료"
fi
echo ""

# 4. 패키지 설치 확인
echo "[4/5] 필수 패키지 확인 중..."
python3 -c "import yfinance, mplfinance, google.generativeai, pandas, PIL" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  일부 패키지가 설치되지 않았습니다."
    echo "   pip install -r requirements.txt를 실행하세요."
else
    echo "✅ 모든 필수 패키지 설치 확인 완료"
fi
echo ""

# 5. 빠른 테스트 실행
echo "[5/5] 빠른 테스트 실행 (quick_test.py)..."
if [ -f "quick_test.py" ]; then
    python3 quick_test.py
else
    echo "⚠️  quick_test.py 파일을 찾을 수 없습니다."
fi
echo ""

echo "===================================="
echo "설정 완료!"
echo "===================================="
echo ""
echo "프로그램 실행 방법:"
echo "1. source venv/bin/activate"
echo "2. export GEMINI_API_KEY='your-api-key-here'  # 또는 영구 설정"
echo "3. python3 main.py"
echo ""
