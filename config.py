import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")


def env(key: str, default: str = "") -> str:
    return os.getenv(key) or default


DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)
ASSETS = ROOT / "assets"
MODELS = DATA / "models"
MODELS.mkdir(exist_ok=True)

# Code display target language
CODE_LANGUAGE = env("CODE_LANGUAGE", "java")

# Channel Branding
CHANNEL_NAME = env("CHANNEL_NAME", "Leetcode_JAVA")

# Narration Language: "en" (English) or "hi" (Hindi / Hinglish)
LANGUAGE = env("LANGUAGE", "en")
HINDI_VOICE = env("HINDI_VOICE", "hi-IN-MadhurNeural")

LLM_PROVIDER = env("LLM_PROVIDER", "gemini")
LLM_MODEL = env("LLM_MODEL", "gemini-2.5-flash")

TTS_PROVIDER = env("TTS_PROVIDER", "kokoro")
KOKORO_VOICE = env("KOKORO_VOICE", "am_michael")
ELEVENLABS_API_KEY = env("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = env("ELEVENLABS_VOICE_ID")

PUBLISH_MODE = env("PUBLISH_MODE", "manual")      # auto | manual
PUBLISH_TIME = env("PUBLISH_TIME", "09:00")
PUBLISH_TZ = env("PUBLISH_TZ", "Asia/Kolkata")
REGION = env("REGION", "IN")
AI_DISCLOSURE = env("AI_DISCLOSURE", "true").lower() != "false"

TOKEN_FILE = ROOT / "token.json"
CLIENT_SECRET_FILE = ROOT / "client_secret.json"