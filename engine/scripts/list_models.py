import os
from google import genai

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY environment variable is not set. Please set it before running this script.")

client = genai.Client(api_key=api_key)

print("Available Gemini models:")
print("=" * 50)

for model in client.models.list():
    print(f"Model: {model.name}")
    print(f"  Display name: {model.display_name}")
    print()
