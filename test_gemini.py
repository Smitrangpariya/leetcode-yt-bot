import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
print("API Key found:", api_key[:8] + "..." if api_key else "NONE")

# Using the active model recommended by the API
url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent"
body = {
    "contents": [{"parts": [{"text": "Respond with JSON only: {\"status\": \"working\"}"}]}],
    "generationConfig": {"responseMimeType": "application/json"}
}

start = time.time()
print("Connecting to Gemini API...")
try:
    r = requests.post(url, json=body, headers={"x-goog-api-key": api_key, "Content-Type": "application/json"}, timeout=30)
    print(f"Status Code: {r.status_code} in {time.time() - start:.2f}s")
    print("Response:", r.text)
except Exception as e:
    print("Failed:", e)