"""Notification dispatcher supporting Telegram and local console output."""
import json
import requests
import config


def _send_telegram(message: str):
    token = config.env("TELEGRAM_BOT_TOKEN")
    chat_id = config.env("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    try:
        requests.post(url, json=payload, timeout=8)
    except Exception:
        pass


def success(problem: dict, video_id: str):
    """Dispatches success notification."""
    pid = problem.get("id", "1")
    title = problem.get("title", "Problem")
    diff = problem.get("difficulty", "Easy")
    yt_url = f"https://youtu.be/{video_id}"

    msg = (
        f"✅ <b>LeetCode #{pid}: {title} ({diff}) Published!</b>\n\n"
        f"Channel: <b>{config.CHANNEL_NAME}</b>\n"
        f"Language: <b>{config.LANGUAGE.upper()}</b>\n"
        f"Link: {yt_url}"
    )
    print(f"\n[NOTIFICATION] {msg}\n")
    _send_telegram(msg)


def failure(problem: dict, error: Exception | str):
    """Dispatches failure notification."""
    pid = problem.get("id", "1")
    title = problem.get("title", "Problem")

    msg = (
        f"❌ <b>LeetCode #{pid}: {title} FAILED!</b>\n\n"
        f"Channel: <b>{config.CHANNEL_NAME}</b>\n"
        f"Error: <code>{str(error)[:400]}</code>"
    )
    print(f"\n[NOTIFICATION] {msg}\n")
    _send_telegram(msg)


# Aliases for compatibility
error = failure
fail = failure