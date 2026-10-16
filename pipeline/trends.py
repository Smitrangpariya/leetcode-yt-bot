"""Research what's working on YouTube right now (free: uses your own API quota, ~200 units/day):
top videos for this problem + the daily-challenge niche, their tags/hashtags, and a visual style
read of the best thumbnails (vision model). We learn PATTERNS and palettes; we never copy thumbnails."""
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
import requests
import config
from . import llm


def research(yt, problem: dict) -> dict:
    empty = {"top": [], "tags": [], "hashtags": [], "style": {}}
    if yt is None:
        return empty
    try:
        after = (datetime.now(timezone.utc) - timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")
        ids: list[str] = []
        for q in (f"leetcode {problem['id']} {problem['title']}", "leetcode daily challenge solution explained"):
            r = yt.search().list(part="id", q=q, type="video", order="viewCount", publishedAfter=after,
                                 maxResults=12, relevanceLanguage="en", regionCode=config.REGION).execute()
            ids += [i["id"]["videoId"] for i in r.get("items", [])]
        ids = list(dict.fromkeys(ids))[:25]
        if not ids:
            return empty
        items = yt.videos().list(part="snippet,statistics", id=",".join(ids)).execute()["items"]
        rows = sorted(({"id": v["id"], "title": v["snippet"]["title"],
                        "views": int(v["statistics"].get("viewCount", 0)),
                        "tags": v["snippet"].get("tags", []),
                        "desc": v["snippet"].get("description", "")} for v in items),
                      key=lambda r: r["views"], reverse=True)[:15]
        tags = Counter(t.lower() for r in rows for t in r["tags"])
        hashes = Counter(h.lower() for r in rows for h in re.findall(r"#(\w{2,30})", r["desc"]))
        top = [{"id": r["id"], "title": r["title"], "views": r["views"]} for r in rows[:8]]
        return {"top": top, "tags": [t for t, _ in tags.most_common(25)],
                "hashtags": [h for h, _ in hashes.most_common(15)], "style": _thumb_style(top[:4])}
    except Exception as e:
        print("Trend research skipped:", e)
        return empty


def _thumb_style(top: list[dict]) -> dict:
    try:
        imgs = []
        for v in top:
            r = requests.get(f"https://i.ytimg.com/vi/{v['id']}/hqdefault.jpg", timeout=20)
            if r.ok:
                imgs.append(r.content)
        if not imgs:
            return {}
        return llm.ask_json(
            "You are a YouTube thumbnail analyst. Reply with ONLY valid JSON.",
            "These are top-performing thumbnails for LeetCode explainer videos. Identify what makes them eye-catching. "
            'Return {"palette":{"bg1":"#hex dark","bg2":"#hex vivid","accent":"#hex bright"},'
            '"notes":"2 sentences on text size, contrast, layout"}. The palette must be inspired by what works '
            "but not copy any single thumbnail.", images=imgs, max_tokens=1500)
    except Exception as e:
        print("Thumbnail style analysis skipped:", e)
        return {}
