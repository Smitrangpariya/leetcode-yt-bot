"""TTS synthesis supporting Cloned Voice, Kokoro, and Edge-TTS with phonetic normalization and retry logic."""
import asyncio
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
import config

try:
    import edge_tts
except ImportError:
    edge_tts = None

CLONE_CLIENT = None


def _get_clone_client():
    global CLONE_CLIENT
    if CLONE_CLIENT is None:
        from gradio_client import Client
        print("Connecting to free Cloud GPU Voice Cloning Space...", flush=True)
        CLONE_CLIENT = Client("mrfakename/E2-F5-TTS")
    return CLONE_CLIENT


def clean_hinglish_for_tts(text: str) -> str:
    """Substitutes English false-friends in Hinglish with clean phonetic anchors."""
    # Prevent spelling out channel name
    t = re.sub(r'\bJAVA\b', 'Java', text)

    # Core Hindi particles
    t = re.sub(r'\bhi\b', 'ही', t, flags=re.IGNORECASE)
    t = re.sub(r'\bhee\b', 'ही', t, flags=re.IGNORECASE)
    t = re.sub(r'\bto\b', 'तो', t, flags=re.IGNORECASE)
    t = re.sub(r'\btoh\b', 'तो', t, flags=re.IGNORECASE)
    t = re.sub(r'\bdo\b', 'दो', t, flags=re.IGNORECASE)
    t = re.sub(r'\bdoh\b', 'दो', t, flags=re.IGNORECASE)

    # Pronunciation fixes
    t = re.sub(r'\bise\b', 'isse', t, flags=re.IGNORECASE)
    t = re.sub(r'\bhue\b', 'huye', t, flags=re.IGNORECASE)

    # Verb patterns
    t = re.sub(r'\buse karenge\b', 'istemaal karenge', t, flags=re.IGNORECASE)
    t = re.sub(r'\buse karein\b', 'istemaal karein', t, flags=re.IGNORECASE)
    t = re.sub(r'\buse karte\b', 'istemaal karte', t, flags=re.IGNORECASE)
    t = re.sub(r'\buse kar\b', 'istemaal kar', t, flags=re.IGNORECASE)
    t = re.sub(r'\buse hota\b', 'istemaal hota', t, flags=re.IGNORECASE)
    
    # Clean greeting interjections
    t = re.sub(r'\bhee!\b', 'Hey!', t, flags=re.IGNORECASE)
    t = re.sub(r'\bhee\s+(kya|doston|aaj)\b', r'Hey \1', t, flags=re.IGNORECASE)

    return t


def _clean_spoken_text(text: str) -> str:
    """Strips markdown and cleans mathematical Big-O notations."""
    t = text.replace("*", "").replace("`", "").replace("_", "")
    t = t.replace("O(N^2)", "O of N squared").replace("O(N)", "O of N").replace("O(1)", "O of 1")
    t = t.replace("O(n^2)", "O of n squared").replace("O(n)", "O of n").replace("O(1)", "O of 1")
    return t.strip()


def get_audio_duration(path: Path) -> float:
    """Calculates audio duration accurately via ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path)
    ]
    p = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(p.stdout.strip())
    except Exception:
        return 3.0


async def _edge_tts_async(text: str, voice: str, output_path: str):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)


def synthesize_edge_tts(text: str, output_path: Path, voice: str = "hi-IN-MadhurNeural") -> float:
    """Synthesizes speech via Edge-TTS with 3 automatic retries and voice fallback."""
    candidate_voices = [voice, "hi-IN-SwaraNeural" if voice == "hi-IN-MadhurNeural" else "hi-IN-MadhurNeural"]

    for attempt in range(1, 4):
        current_voice = candidate_voices[(attempt - 1) % len(candidate_voices)]
        try:
            asyncio.run(_edge_tts_async(text, current_voice, str(output_path)))
            dur = get_audio_duration(output_path)
            if dur > 0.2:
                return dur
        except Exception as e:
            if attempt < 3:
                wait_time = 1.5 * attempt
                time.sleep(wait_time)
            else:
                raise RuntimeError(f"Edge-TTS failed after 3 attempts: {e}") from e

    return get_audio_duration(output_path)


def synthesize_cloned_voice(text: str, output_path: Path) -> float:
    """Zero-cost cloud GPU voice cloning using your assets/voice_sample.wav."""
    from gradio_client import handle_file

    if not config.VOICE_SAMPLE_PATH.exists():
        raise FileNotFoundError(f"Voice sample not found at: {config.VOICE_SAMPLE_PATH.resolve()}")

    client = _get_clone_client()
    result = client.predict(
        ref_audio_orig=handle_file(str(config.VOICE_SAMPLE_PATH.resolve())),
        ref_text="",
        gen_text=text,
        model="F5-TTS",
        remove_silence=True,
        api_name="/basic_tts"
    )

    shutil.copy(result[0], str(output_path))
    return get_audio_duration(output_path)


def synthesize(text: str, output_path: Path) -> float:
    """Main synthesis entry point."""
    cleaned = _clean_spoken_text(text)

    # 1. Hindi / Hinglish Voice with phonetic normalization
    if config.LANGUAGE.lower() in ("hi", "hindi"):
        phonetic_text = clean_hinglish_for_tts(cleaned)
        return synthesize_edge_tts(phonetic_text, output_path, voice=config.HINDI_VOICE)

    # 2. Cloned Voice (Cloud GPU)
    if config.TTS_PROVIDER == "cloned":
        try:
            return synthesize_cloned_voice(cleaned, output_path)
        except Exception as e:
            print(f"[Warning] Cloned voice failed ({e}), falling back to neural voice...", flush=True)

    # 3. English Fallback
    return synthesize_edge_tts(cleaned, output_path, voice="en-US-ChristopherNeural")


def combine_audios(audio_files: list[Path], output_path: Path):
    """Combines individual mp3/wav files into one continuous track."""
    existing = [f for f in audio_files if f.exists() and f.stat().st_size > 0]
    if not existing:
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "1", str(output_path)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return

    filter_complex = "".join(f"[{i}:a]" for i in range(len(existing))) + f"concat=n={len(existing)}:v=0:a=1[out]"
    cmd = ["ffmpeg", "-y"]
    for f in existing:
        cmd.extend(["-i", str(f)])
    cmd.extend(["-filter_complex", filter_complex, "-map", "[out]", str(output_path)])
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)