"""Manual control. Usage:
  python review.py list
  python review.py hold <video_id>            # stays private, schedule removed
  python review.py publish <video_id>         # public right now
  python review.py reschedule <video_id> "2026-10-14 09:00"   # local time in PUBLISH_TZ
  python review.py delete <video_id>
"""
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
import config
from pipeline import notify, youtube


def main(argv: list[str]) -> None:
    action = argv[0] if argv else "list"
    vid = argv[1] if len(argv) > 1 else ""
    when = argv[2] if len(argv) > 2 else ""
    yt = youtube.service()
    if action == "list":
        for v in youtube.recent_uploads(yt, 15):
            sched = f"  goes public {v['publishAt']}" if v["publishAt"] else ""
            print(f"{v['id']}  [{v['privacy']}]{sched}  {v['title']}")
        return
    if not vid:
        raise SystemExit("video id required")
    if action == "hold":
        youtube.update_status(yt, vid, "private")
        msg = f"Held {vid}: it stays private. Publish later with action=publish."
    elif action == "publish":
        youtube.update_status(yt, vid, "public")
        msg = f"Published {vid} now: https://youtu.be/{vid}"
    elif action == "reschedule":
        t = datetime.strptime(when, "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo(config.PUBLISH_TZ))
        youtube.update_status(yt, vid, "private", t)
        msg = f"Rescheduled {vid} for {when} {config.PUBLISH_TZ}"
    elif action == "delete":
        youtube.delete(yt, vid)
        msg = f"Deleted {vid}"
    else:
        raise SystemExit(f"unknown action {action}")
    print(msg)
    notify.send(msg)


if __name__ == "__main__":
    main(sys.argv[1:])
