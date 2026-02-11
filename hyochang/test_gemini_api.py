#!/usr/bin/env python3
"""
Gemini API 연결 테스트
"""

import os
import google.generativeai as genai

# API 키 확인
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not GEMINI_API_KEY or GEMINI_API_KEY == "your-api-key-here":
    print("❌ GEMINI_API_KEY가 설정되지 않았습니다.")
    print("   export GEMINI_API_KEY='your-key' 명령어로 설정하세요.")
    exit(1)

print(f"✅ API Key: {GEMINI_API_KEY[:20]}...")

# Gemini API 설정
genai.configure(api_key=GEMINI_API_KEY)

# 사용 가능한 모델 확인
print("\n사용 가능한 모델 목록:")
for model in genai.list_models():
    if 'generateContent' in model.supported_generation_methods:
        print(f"  - {model.name}")

# gemini-2.5-flash 테스트
try:
    print("\n🧪 gemini-2.5-flash 모델 테스트 중...")
    model = genai.GenerativeModel('gemini-2.5-flash')
    response = model.generate_content("Hello, please respond with 'API test successful!'")
    print(f"✅ 응답: {response.text}")
    print("\n🎉 Gemini API 연결 성공!")
except Exception as e:
    print(f"❌ 오류: {e}")
    print("\n다른 모델 시도 중...")
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content("Hello, please respond with 'API test successful!'")
        print(f"✅ gemini-1.5-flash 응답: {response.text}")
    except Exception as e2:
        print(f"❌ gemini-1.5-flash 오류: {e2}")
