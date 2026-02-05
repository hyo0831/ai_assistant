import os
import google.generativeai as genai

api_key = os.environ.get("GEMINI_API_KEY", "AIzaSyD2f3jsLwMqR4dt6fy8tOU_QCBSO3NVGmc")
genai.configure(api_key=api_key)

print("Available Gemini models:")
print("=" * 50)

for model in genai.list_models():
    if 'generateContent' in model.supported_generation_methods:
        print(f"Model: {model.name}")
        print(f"  Display name: {model.display_name}")
        print(f"  Supported methods: {model.supported_generation_methods}")
        print()
