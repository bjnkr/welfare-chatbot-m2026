import google.generativeai as genai
import os
import toml

# secrets.toml 파일 읽기
try:
    data = toml.load(".streamlit/secrets.toml")
    # API 키의 공백/줄바꿈 제거가 핵심
    api_key = data["GEMINI_API_KEY"].strip()
    print(f"API Key found (stripped): {api_key[:5]}...")
except Exception as e:
    print(f"Failed to load secrets: {e}")
    # try to assume user might have passed it in env or just hardcode for test if toml fails? 
    # No, strictly check toml as that's what app uses.
    exit(1)

genai.configure(api_key=api_key)

print("Testing Gemini 1.5 Flash...")
try:
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content("Hello, this is a test. Just say OK.")
    print(f"Response: {response.text}")
    print("SUCCESS: Gemini 1.5 Flash is working.")
except Exception as e:
    print(f"ERROR: {e}")

print("-" * 20)
print("Testing Gemini 2.0 Flash Exp...")
try:
    model = genai.GenerativeModel("gemini-2.0-flash-exp")
    response = model.generate_content("Hello, this is a test. Just say OK.")
    print(f"Response: {response.text}")
    print("SUCCESS: Gemini 2.0 Flash Exp is working.")
except Exception as e:
    print(f"ERROR: {e}")
