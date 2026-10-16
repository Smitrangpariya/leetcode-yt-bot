import os
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

print(f"Checking active models for key: {api_key[:8]}...")
url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
res = requests.get(url, timeout=15)

if res.status_code != 200:
    print(f"Error fetching models: {res.text}")
    exit(1)

models = res.json().get("models", [])
available = [
    m["name"].replace("models/", "")
    for m in models
    if "generateContent" in m.get("supportedGenerationMethods", [])
]

print(f"\nFound {len(available)} models supporting generateContent:")
for name in available:
    print(f" - {name}")

# Test top flash candidates
print("\nTesting candidate responsiveness...")
for candidate in ["gemini-3.8-flash", "gemini-2.5-flash", "gemini-1.5-flash"]:
    if candidate in available:
        test_url = f"https://generativelanguage.googleapis.com/v1beta/models/{candidate}:generateContent"
        body = {
            "contents": [{"parts": [{"text": "Reply: {\"ok\": true}"}]}],
            "generationConfig": {"responseMimeType": "application/json"}
        }
        try:
            r = requests.post(test_url, json=body, headers={"x-goog-api-key": api_key, "Content-Type": "application/json"}, timeout=15)
            if r.status_code == 200:
                print(f"✓ {candidate}: ONLINE and READY (Status 200)")
            else:
                print(f"✗ {candidate}: HTTP {r.status_code} ({r.json().get('error', {}).get('message', '')[:50]})")
        except Exception as e:
            print(f"✗ {candidate}: Timeout or Connection Error")