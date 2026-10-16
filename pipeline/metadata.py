"""Generates YouTube title, thumbnail hook text, SEO tags, and timestamped descriptions with local caching."""
import json
import re
from pathlib import Path
from . import llm
import config

PALETTES = [
    {"bg1": "#1b1464", "bg2": "#0f7bff", "accent": "#ffd400"},
    {"bg1": "#2b0a3d", "bg2": "#ff3d71", "accent": "#fff176"},
    {"bg1": "#06283d", "bg2": "#00c2a8", "accent": "#ffe14d"},
    {"bg1": "#2d1b00", "bg2": "#ff7a18", "accent": "#ffffff"},
]


def _get_instant_metadata(problem: dict, sol: dict) -> dict:
    """Instant high-CTR, SEO-optimized metadata (0 API tokens used)."""
    pid = str(problem.get("id", "1"))
    title = problem.get("title", "Two Sum")
    diff = problem.get("difficulty", "Easy")
    slug = problem.get("slug", "two-sum")

    palette_idx = int(pid) % len(PALETTES) if pid.isdigit() else 0
    palette = PALETTES[palette_idx]

    is_hindi = config.LANGUAGE.lower() in ("hi", "hindi")
    lang_tag = " (Hindi)" if is_hindi else ""
    sub_tag = "JAVA HINDI TUTORIAL" if is_hindi else "ALL APPROACHES IN JAVA"

    clean_slug = slug.replace("-", "")
    return {
        "title": f"LeetCode {pid}: {title} in Java{lang_tag} | Brute Force to Optimal Explained",
        "thumb_text": "TWO SUM SOLVED",
        "thumb_sub": sub_tag,
        "palette": palette,
        "hashtags": [
            "leetcode",
            "java",
            "dsa",
            "codinginterview",
            clean_slug,
            "hindi" if is_hindi else "programming"
        ],
        "tags": [
            f"leetcode {pid}",
            title,
            f"{title} java",
            f"leetcode {pid} java",
            "two sum java",
            "two sum in hindi" if is_hindi else "two sum explained",
            "leetcode java",
            "dsa in java",
            "coding interview preparation"
        ],
        "hook_line": sol.get("hook", f"Complete Java solution for LeetCode {pid} {title}.")
    }


def build(problem: dict, sol: dict, work_dir: Path | None = None) -> dict:
    """Loads cached metadata if available, otherwise generates instant SEO metadata."""
    cache_file = (work_dir / "metadata.json") if work_dir else None

    # 1. Reuse cache if available
    if cache_file and cache_file.exists():
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            if data.get("title") and data.get("thumb_text"):
                print("✓ Found cached metadata. Skipping LLM API call!")
                return data
        except Exception:
            pass

    # 2. Return instant SEO metadata without burning Gemini quota
    meta = _get_instant_metadata(problem, sol)

    if cache_file:
        cache_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    return meta


# Compatibility aliases
make = build
generate = build
create = build


def build_description(problem: dict, sol: dict, meta: dict, chapters: list[str]) -> str:
    """Builds a formatted YouTube video description with chapter timestamps and Java code."""
    pid = str(problem.get("id", "1"))
    title = problem.get("title", "Problem")
    diff = problem.get("difficulty", "Easy")
    url = problem.get("url", f"https://leetcode.com/problems/{problem.get('slug', '')}/")
    is_hindi = config.LANGUAGE.lower() in ("hi", "hindi")

    desc_lines = [
        f"Master LeetCode #{pid}: {title} ({diff}) in Java{' [Hindi]' if is_hindi else ''}!",
        "",
        meta.get("hook_line", sol.get("hook", "")),
        "",
        "🔗 Problem Link:",
        url,
        "",
        "⏱️ Timestamps & Chapters:"
    ]

    for ch in chapters:
        desc_lines.append(ch)

    desc_lines.extend([
        "",
        "💡 Approaches Covered:"
    ])

    for i, a in enumerate(sol.get("approaches", []), 1):
        desc_lines.append(f"{i}. {a.get('name', 'Approach')} — Time: {a.get('time', 'O(N)')} | Space: {a.get('space', 'O(1)')}")
        if a.get("idea"):
            desc_lines.append(f"   {a.get('idea')}")

    optimal_approach = sol.get("approaches", [])[-1] if sol.get("approaches") else {}
    java_code = optimal_approach.get("java_code", "")
    if java_code:
        desc_lines.extend([
            "",
            "💻 Optimal Java Solution:",
            "```java",
            java_code.strip(),
            "```"
        ])

    hashtags = meta.get("hashtags", ["leetcode", "java", "dsa", "codinginterview"])
    tag_str = " ".join(f"#{t.lstrip('#')}" for t in hashtags[:6])
    desc_lines.extend([
        "",
        tag_str
    ])

    if config.AI_DISCLOSURE:
        desc_lines.extend([
            "",
            "---",
            "This video presentation and narration were generated using automated developer tooling."
        ])

    return "\n".join(desc_lines)