"""Offline logic tests with stand-ins for the network (no keys needed): python scripts/selftest.py"""
import copy
import sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from pipeline import llm, metadata, solver, trends, verifier, youtube
from scripts.demo_offline import PROBLEM, SOL

ok = 0


def check(name, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + name)
    ok += bool(cond)
    assert cond, name


# 1. verifier rejects a wrong approach, bad step lines, over-long code
bad = copy.deepcopy(SOL)
bad["approaches"][1]["code"] = "def solution(nums, target):\n    return [0, 1]"
try:
    verifier.verify(bad); check("verifier catches disagreeing approach", False)
except verifier.VerifyError:
    check("verifier catches disagreeing approach", True)
bad = copy.deepcopy(SOL)
bad["approaches"][0]["steps"][0]["lines"] = [1, 99]
try:
    verifier.verify(bad); check("verifier catches bad step line range", False)
except verifier.VerifyError:
    check("verifier catches bad step line range", True)

# 2. solver retries: first LLM answer broken, second good
calls = []
def fake_llm(system, user, images=None, max_tokens=0):
    calls.append(user)
    return bad if len(calls) == 1 else SOL
llm.ask_json = fake_llm
sol, res = solver.generate_verified(PROBLEM)
check("solver retries after failed verification", len(calls) == 2 and "failed verification" in calls[1])

# 3. tracer returns real variable values
ev = verifier.trace(SOL["approaches"][1]["code"], SOL["tests"][0])
check("tracer records line events with locals", len(ev) > 5 and "need" in ev[-1][1] or any("need" in e[1] for e in ev))

# 4. metadata falls back safely when the LLM fails, and sanitizes output
def boom(*a, **k): raise RuntimeError("no network")
llm.ask_json = boom
m = metadata.generate(PROBLEM, SOL, {"top": [], "tags": [], "hashtags": [], "style": {}})
check("metadata fallback title has problem id", "LeetCode 1" in m["title"] and m["hashtags"])
llm.ask_json = lambda *a, **k: {"title": "Why <b>Two Sum</b> is easy", "hashtags": ["#Two Sum!", "dsa"] * 10, "tags": ["x" * 40] * 30}
m = metadata.generate(PROBLEM, SOL, {})
check("metadata sanitizes title/hashtags/tags", "<" not in m["title"] and "LeetCode 1" in m["title"]
      and len(m["hashtags"]) <= 12 and sum(len(t) + 1 for t in m["tags"]) < 500)

# 5. trends with a stub YouTube client + stub thumbnails
class Exec:
    def __init__(self, v): self.v = v
    def execute(self): return self.v
class Search:
    def list(self, **k): return Exec({"items": [{"id": {"videoId": f"v{i}"}} for i in range(5)]})
class Videos:
    def list(self, **k):
        return Exec({"items": [{"id": f"v{i}", "snippet": {"title": f"T{i}", "tags": ["leetcode", f"t{i}"],
                      "description": "#leetcode #dsa"}, "statistics": {"viewCount": str(100 * i)}} for i in range(5)]})
class YT:
    def search(self): return Search()
    def videos(self): return Videos()
trends._thumb_style = lambda top: {"palette": {"bg1": "#000000"}, "notes": "stub"}
t = trends.research(YT(), PROBLEM)
check("trends ranks by views and counts tags", t["top"][0]["views"] == 400 and t["tags"][0] == "leetcode"
      and "dsa" in t["hashtags"])
check("trends returns empty (no crash) without a client", trends.research(None, PROBLEM)["top"] == [])

# 6. exact publish-time logic (09:00 Asia/Kolkata == 03:30 UTC)
config.PUBLISH_TIME, config.PUBLISH_TZ = "09:00", "Asia/Kolkata"
t1 = youtube.next_publish_time(datetime(2026, 10, 14, 0, 40, tzinfo=timezone.utc))
check("publishes at 03:30 UTC same day when on schedule", t1 == datetime(2026, 10, 14, 3, 30, tzinfo=timezone.utc))
t2 = youtube.next_publish_time(datetime(2026, 10, 14, 4, 0, tzinfo=timezone.utc))
check("if running late, publishes ~20 min after upload (not a day late)",
      (t2 - datetime(2026, 10, 14, 4, 0, tzinfo=timezone.utc)).total_seconds() == 1200)
t3 = youtube.next_publish_time(datetime(2026, 10, 14, 10, 0, tzinfo=timezone.utc))
check("if target passed long ago, schedules next day", t3 == datetime(2026, 10, 15, 3, 30, tzinfo=timezone.utc))

print(f"\n{ok} checks passed")
