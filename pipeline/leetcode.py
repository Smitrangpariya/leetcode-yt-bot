"""Fetches LeetCode problems in sequence (1, 2, 3...) with persistent sequence tracking."""
import json
import re
import time
from pathlib import Path
import requests
import config

URL = "https://leetcode.com/graphql"
SEQUENCE_FILE = config.DATA / "sequence.json"

HEADERS = {
    "Content-Type": "application/json",
    "Referer": "https://leetcode.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

KNOWN_SLUGS = {
    1: "two-sum",
    2: "add-two-numbers",
    3: "longest-substring-without-repeating-characters",
    4: "median-of-two-sorted-arrays",
    5: "longest-palindromic-substring",
    6: "zigzag-conversion",
    7: "reverse-integer",
    8: "string-to-integer-atoi",
    9: "palindrome-number",
    10: "regular-expression-matching",
    11: "container-with-most-water",
    12: "integer-to-roman",
    13: "roman-to-integer",
    14: "longest-common-prefix",
    15: "3sum",
    16: "3sum-closest",
    17: "letter-combinations-of-a-phone-number",
    18: "4sum",
    19: "remove-nth-node-from-end-of-list",
    20: "valid-parentheses",
    21: "merge-two-sorted-lists",
    22: "generate-parentheses",
    23: "merge-k-sorted-lists",
    24: "swap-nodes-in-pairs",
    25: "reverse-nodes-in-k-group",
    26: "remove-duplicates-from-sorted-array",
    27: "remove-element",
    28: "find-the-index-of-the-first-occurrence-in-a-string",
    29: "divide-two-integers",
    30: "substring-with-concatenation-of-all-words",
    31: "next-permutation",
    32: "longest-valid-parentheses",
    33: "search-in-rotated-sorted-array",
    34: "find-first-and-last-position-of-element-in-sorted-array",
    35: "search-insert-position",
    36: "valid-sudoku",
    37: "sudoku-solver",
    38: "count-and-say",
    39: "combination-sum",
    40: "combination-sum-ii",
    41: "first-missing-positive",
    42: "trapping-rain-water",
    43: "multiply-strings",
    44: "wildcard-matching",
    45: "jump-game-ii",
    46: "permutations",
    47: "permutations-ii",
    48: "rotate-image",
    49: "group-anagrams",
    50: "powx-n"
}

QUERY_QUESTION = """
query getQuestionDetail($titleSlug: String!) {
  question(titleSlug: $titleSlug) {
    questionFrontendId
    title
    titleSlug
    difficulty
    content
    topicTags {
      name
    }
  }
}
"""

QUERY_SEARCH_SLUG = """
query problemsetQuestionList($categorySlug: String, $limit: Int, $skip: Int, $filters: QuestionListFilterInput) {
  problemsetQuestionList: questionList(
    categorySlug: $categorySlug
    limit: $limit
    skip: $skip
    filters: $filters
  ) {
    questions: data {
      questionFrontendId
      title
      titleSlug
    }
  }
}
"""


def clean_html(raw_html: str) -> str:
    if not raw_html:
        return ""
    clean = re.sub(r"<[^>]+>", "", raw_html)
    return clean.replace("&nbsp;", " ").replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&").replace("&quot;", '"').strip()


def get_current_sequence_id() -> int:
    """Reads current sequence number from sequence.json (defaults to 1)."""
    if SEQUENCE_FILE.exists():
        try:
            data = json.loads(SEQUENCE_FILE.read_text(encoding="utf-8"))
            return int(data.get("next_id", 1))
        except Exception:
            pass
    return 1


def advance_sequence(completed_id: int):
    """Increments the sequence tracker to the next problem number."""
    state = {"next_id": completed_id + 1, "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")}
    if SEQUENCE_FILE.exists():
        try:
            old = json.loads(SEQUENCE_FILE.read_text(encoding="utf-8"))
            hist = old.get("history", [])
            if completed_id not in hist:
                hist.append(completed_id)
            state["history"] = hist
        except Exception:
            state["history"] = [completed_id]
    else:
        state["history"] = [completed_id]

    SEQUENCE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(f"✓ Sequence pointer advanced: Next problem is #{state['next_id']}")


def _resolve_slug(problem_id: int) -> str:
    if problem_id in KNOWN_SLUGS:
        return KNOWN_SLUGS[problem_id]

    body = {
        "query": QUERY_SEARCH_SLUG,
        "variables": {"categorySlug": "", "skip": 0, "limit": 50, "filters": {"searchKeywords": str(problem_id)}}
    }
    r = requests.post(URL, json=body, headers=HEADERS, timeout=20)
    r.raise_for_status()
    items = r.json().get("data", {}).get("problemsetQuestionList", {}).get("questions", [])
    for it in items:
        if str(it.get("questionFrontendId")) == str(problem_id):
            return it["titleSlug"]
    raise ValueError(f"Could not resolve title slug for LeetCode #{problem_id}")


def fetch_problem_by_id(problem_id: int) -> dict:
    slug = _resolve_slug(problem_id)
    print(f"Connecting to LeetCode for Problem #{problem_id} ('{slug}')...")

    body = {"query": QUERY_QUESTION, "variables": {"titleSlug": slug}}
    r = requests.post(URL, json=body, headers=HEADERS, timeout=20)
    r.raise_for_status()
    q = r.json().get("data", {}).get("question")
    if not q:
        raise ValueError(f"Empty data received for #{problem_id}")

    return {
        "id": str(q.get("questionFrontendId", problem_id)),
        "title": q["title"],
        "slug": q["titleSlug"],
        "difficulty": q["difficulty"],
        "topics": [t["name"] for t in q.get("topicTags", [])],
        "url": f"https://leetcode.com/problems/{q['titleSlug']}/",
        "date": time.strftime("%Y-%m-%d"),
        "content": clean_html(q.get("content", ""))
    }


def fetch_daily(problem_id: int | None = None) -> dict:
    target_id = problem_id if problem_id is not None else get_current_sequence_id()
    return fetch_problem_by_id(target_id)