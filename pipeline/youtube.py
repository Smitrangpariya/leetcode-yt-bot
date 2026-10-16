"""YouTube Data API v3 uploader supporting OAuth2, metadata, custom thumbnails, and scheduling."""
import datetime
import json
import os
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


def _get_authenticated_service():
    """Authenticates with YouTube API using token.json (headless in CI) or client_secret.json (local)."""
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
                raise FileNotFoundError(f"Missing {config.CLIENT_SECRET_FILE}. Download it from Google Cloud Console.")

            flow = InstalledAppFlow.from_client_secrets_file(str(config.CLIENT_SECRET_FILE), SCOPES)
            creds = flow.run_local_server(port=0)

        config.TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")

    return build("youtube", "v3", credentials=creds)


def upload(video_path: Path, thumb_path: Path | None = None, meta: dict | None = None, publish_at: str | None = None, **kwargs) -> str:
    """
    Uploads video to YouTube with title, description, tags, and thumbnail.
    Accepts both positional and keyword arguments safely.
    """
    # Fallback argument mapping in case arguments are passed differently
    video = Path(kwargs.get("video", video_path))
    thumb = Path(kwargs.get("thumb", thumb_path)) if (thumb_path or "thumb" in kwargs) else None
    metadata = kwargs.get("meta", meta) or {}

    if not video.exists():
        raise FileNotFoundError(f"Video file not found: {video}")

    title = metadata.get("title", f"LeetCode Solution - {config.CHANNEL_NAME}")[:100]
    description = metadata.get("description", "Daily LeetCode Solution in Java.")
    tags = metadata.get("tags", ["leetcode", "java", "dsa", "coding interview"])

    # Determine privacy status
    if publish_at:
        privacy_status = "private"
    elif config.PUBLISH_MODE.lower() == "auto":
        privacy_status = "public"
    else:
        # Default to unlisted for manual review
        privacy_status = "unlisted"

    status_body = {
        "privacyStatus": privacy_status,
        "selfDeclaredMadeForKids": False
    }

    if publish_at:
        status_body["publishAt"] = publish_at

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags[:30],
            "categoryId": "27"  # Education category
        },
        "status": status_body
    }

    print("Authenticating with YouTube API...", flush=True)
    youtube = _get_authenticated_service()

    print(f"Uploading '{video.name}' to YouTube ({privacy_status})...", flush=True)
    media = MediaFileUpload(str(video), mimetype="video/mp4", resumable=True, chunksize=1024 * 1024 * 4)

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  Upload progress: {int(status.progress() * 100)}%", flush=True)

    video_id = response.get("id")
    print(f"✓ Video uploaded successfully! Video ID: {video_id}", flush=True)

    # Set custom thumbnail if provided
    if thumb and thumb.exists():
        try:
            print(f"Setting custom thumbnail from '{thumb.name}'...", flush=True)
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(str(thumb), mimetype="image/jpeg")
            ).execute()
            print("✓ Thumbnail attached successfully!", flush=True)
        except Exception as e:
            print(f"[Warning] Failed to set thumbnail ({e}). You can set it manually in YouTube Studio.", flush=True)

    return video_id