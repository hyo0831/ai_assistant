import os
import google.generativeai as genai

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY environment variable is not set. Please set it before running this script.")
genai.configure(api_key=api_key)

print("Available Gemini models:")
print("=" * 50)

for model in genai.list_models():
    if 'generateContent' in model.supported_generation_methods:
        print(f"Model: {model.name}")
        print(f"  Display name: {model.display_name}")
        print(f"  Supported methods: {model.supported_generation_methods}")
        print()
