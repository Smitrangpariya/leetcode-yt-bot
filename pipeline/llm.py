"""LLM wrapper with multi-model fallback prioritizing high-quota Flash-Lite models."""
import json
import os
import re
import time
import requests
import config

MODEL_CANDIDATES = [
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash-lite",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
]


def _extract_json(text: str) -> dict:
    """Extracts JSON object cleanly even if wrapped in markdown fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        cleaned = cleaned[start : end + 1]
    return json.loads(cleaned)


def ask_json(system: str, user_prompt: str) -> dict:
    """Requests structured JSON from Gemini REST API with automatic model rotation."""
    api_key = config.env("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing in .env or environment variables.")

    preferred = config.LLM_MODEL
    models = [preferred] + [m for m in MODEL_CANDIDATES if m != preferred]

    for model in models:
        # CLEAN URL WITHOUT ANY MARKDOWN BRACKETS
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "temperature": 0.3,
                "responseMimeType": "application/json",
            },
        }

        for attempt in range(1, 3):
            try:
                print(f"Requesting solution from '{model}'...", flush=True)
                resp = requests.post(url, json=payload, timeout=90)

                if resp.status_code == 429:
                    wait = 15 * attempt
                    print(f"[Warning] '{model}' rate limited (429). Cooling down {wait}s...", flush=True)
                    time.sleep(wait)
                    continue

                if resp.status_code in (400, 404):
                    print(f"[Info] '{model}' unavailable ({resp.status_code}). Trying next model...", flush=True)
                    break

                resp.raise_for_status()
                data = resp.json()
                raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                parsed = _extract_json(raw_text)
                print(f"✓ Solution successfully generated using '{model}'!", flush=True)
                return parsed

            except (KeyError, IndexError, json.JSONDecodeError) as e:
                print(f"[Warning] Malformed JSON from '{model}' ({e}). Retrying...", flush=True)
            except requests.RequestException as e:
                print(f"[Warning] Network error on '{model}' ({e}).", flush=True)
                break

    raise RuntimeError("All Gemini model candidates failed or timed out.")
