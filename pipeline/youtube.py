"""YouTube Data API v3 uploader with OAuth2, metadata sanitization, and thumbnails."""
import os
import re
from pathlib import Path

import config

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
except ImportError:
    pass

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]


def _remove_control_characters(value: str) -> str:
    """Remove control characters that should not be sent as video metadata."""
    # Preserve normal newlines and tabs; normalize CRLF/CR to LF first.
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    return "".join(
        ch for ch in value
        if ch in "\n\t" or ord(ch) >= 32 and not 127 <= ord(ch) <= 159
    )


def _sanitize_youtube_title(value: str, max_chars: int = 100) -> str:
    """YouTube titles must be <=100 characters and cannot contain literal < or >."""
    text = _remove_control_characters(str(value or ""))
    text = text.replace("<", "&lt;").replace(">", "&gt;").strip()
    return text[:max_chars]


def _sanitize_youtube_description(value: str, max_bytes: int = 4900) -> str:
    """Make a YouTube description API-safe and leave headroom under 5,000 UTF-8 bytes.

    YouTube's videos.insert API rejects literal '<' and '>' in descriptions.
    Convert them to text entities, remove disallowed control characters, and
    truncate safely on a UTF-8 character boundary if necessary.
    """
    text = _remove_control_characters(str(value or ""))
    text = text.replace("<", "&lt;").replace(">", "&gt;").strip()

    encoded = text.encode("utf-8")
    if len(encoded) > max_bytes:
        encoded = encoded[:max_bytes]
        text = encoded.decode("utf-8", errors="ignore").rstrip()
        # Don't leave a partial line at the end when truncating a long description.
        if "\n" in text:
            text = text.rsplit("\n", 1)[0].rstrip()

    # Defensive invariants: fail locally with a clear error instead of sending
    # an invalid description to YouTube and receiving opaque invalidDescription.
    if "<" in text or ">" in text:
        raise ValueError("YouTube description sanitizer left a prohibited angle bracket")
    if len(text.encode("utf-8")) > 5000:
        raise ValueError("YouTube description exceeds the 5,000-byte limit after sanitization")
    return text


def _get_authenticated_service():
    """Authenticate with YouTube API using token.json in CI or client_secret.json locally."""
    creds = None

    if config.TOKEN_FILE.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(config.TOKEN_FILE), SCOPES)
        except Exception as e:
            print(f"[Warning] Could not load token.json ({e}). Re-authenticating...", flush=True)
            creds = None

    if not creds or not creds.valid:
        refreshed = False
        if creds and creds.expired and creds.refresh_token:
            try:
                print("Refreshing YouTube OAuth token...", flush=True)
                creds.refresh(Request())
                refreshed = True
            except Exception as e:
                print(f"[Warning] Token refresh failed ({e}). Starting fresh OAuth flow...", flush=True)
                creds = None

        if not refreshed:
            if os.getenv("GITHUB_ACTIONS") == "true":
                raise RuntimeError(
                    "token.json is missing, expired, or has invalid_scope in GitHub Actions! "
                    "Delete token.json locally, regenerate it, and update the YOUTUBE_TOKEN_JSON secret."
                )
            if not config.CLIENT_SECRET_FILE.exists():
                raise FileNotFoundError(
                    f"Missing {config.CLIENT_SECRET_FILE}. Download it from Google Cloud Console."
                )

            flow = InstalledAppFlow.from_client_secrets_file(str(config.CLIENT_SECRET_FILE), SCOPES)
            creds = flow.run_local_server(port=0)

        config.TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")

    return build("youtube", "v3", credentials=creds)


def upload(
    video_path: Path,
    thumb_path: Path | None = None,
    meta: dict | None = None,
    publish_at: str | None = None,
    **kwargs,
) -> str:
    """Upload video with sanitized metadata, then set its custom thumbnail if available."""
    video = Path(kwargs.get("video", video_path))
    thumb_arg = kwargs.get("thumb", thumb_path)
    thumb = Path(thumb_arg) if thumb_arg else None
    metadata = kwargs.get("meta", meta) or {}

    if not video.exists():
        raise FileNotFoundError(f"Video file not found: {video}")

    title = _sanitize_youtube_title(
        metadata.get("title", f"LeetCode Solution - {config.CHANNEL_NAME}")
    )
    description = _sanitize_youtube_description(
        metadata.get("description", "Daily LeetCode Solution in Java.")
    )
    raw_tags = metadata.get("tags", ["leetcode", "java", "dsa", "coding interview"])
    tags = []
    for tag in raw_tags[:30]:
        clean_tag = _remove_control_characters(str(tag or ""))
        clean_tag = clean_tag.replace("<", "&lt;").replace(">", "&gt;").strip()
        if clean_tag:
            tags.append(clean_tag)

    print(
        "[YouTube] Metadata validated: "
        f"title={len(title)} chars, "
        f"description={len(description.encode('utf-8'))} UTF-8 bytes, "
        f"tags={len(tags)}; prohibited angle brackets in title/description: "
        f"{'<' in title or '>' in title or '<' in description or '>' in description}",
        flush=True,
    )

    if not title:
        raise ValueError("YouTube title is empty after sanitization")
    if not description:
        raise ValueError("YouTube description is empty after sanitization")

    if publish_at:
        privacy_status = "private"
    elif config.PUBLISH_MODE.lower() == "auto":
        privacy_status = "public"
    else:
        # Preserve existing manual-review behavior.
        privacy_status = "unlisted"

    status_body = {
        "privacyStatus": privacy_status,
        "selfDeclaredMadeForKids": False,
    }
    if publish_at:
        status_body["publishAt"] = publish_at

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "27",
        },
        "status": status_body,
    }

    print("Authenticating with YouTube API...", flush=True)
    youtube = _get_authenticated_service()

    print(f"Uploading '{video.name}' to YouTube ({privacy_status})...", flush=True)
    media = MediaFileUpload(
        str(video), mimetype="video/mp4", resumable=True, chunksize=1024 * 1024 * 4
    )
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  Upload progress: {int(status.progress() * 100)}%", flush=True)

    video_id = response.get("id")
    if not video_id:
        raise RuntimeError("YouTube upload returned no video ID")
    print(f"✓ Video uploaded successfully! Video ID: {video_id}", flush=True)

    if thumb and thumb.exists():
        try:
            print(f"Setting custom thumbnail from '{thumb.name}'...", flush=True)
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(str(thumb), mimetype="image/jpeg"),
            ).execute()
            print("✓ Thumbnail attached successfully!", flush=True)
        except Exception as e:
            print(
                f"[Warning] Failed to set thumbnail ({e}). You can set it manually in YouTube Studio.",
                flush=True,
            )

    return video_id
