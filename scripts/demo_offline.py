"""Offline demo: renders a full sample video + thumbnail for Two Sum with NO API keys and no uploads.
  TTS_PROVIDER=preview python scripts/demo_offline.py     # silent, ~20 seconds, checks layouts
  python scripts/demo_offline.py                          # with real audio voice
"""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from pipeline import metadata, render, scenes, thumbnail, verifier

PROBLEM = {"id": "1", "title": "Two Sum", "slug": "demo-two-sum", "difficulty": "Easy",
           "topics": ["Array", "Hash Table"], "url": "https://leetcode.com/problems/two-sum/", "date": "2026-10-13",
           "content": ""}

BRUTE = """def solution(nums, target):
    n = len(nums)
    for i in range(n):
        for j in range(i + 1, n):
            # try every pair
            if nums[i] + nums[j] == target:
                return [i, j]
    return []"""

BRUTE_JAVA = """public int[] twoSum(int[] nums, int target) {
    int n = nums.length;
    for (int i = 0; i < n; i++) {
        for (int j = i + 1; j < n; j++) {
            if (nums[i] + nums[j] == target) {
                return new int[]{i, j};
            }
        }
    }
    return new int[]{};
}"""

HASH = """def solution(nums, target):
    seen = {}  # value -> index
    for i, x in enumerate(nums):
        need = target - x
        if need in seen:
            return [seen[need], i]
        seen[x] = i
    return []"""

HASH_JAVA = """public int[] twoSum(int[] nums, int target) {
    Map<Integer, Integer> seen = new HashMap<>();
    for (int i = 0; i < nums.length; i++) {
        int need = target - nums[i];
        if (seen.containsKey(need)) {
            return new int[]{seen.get(need), i};
        }
        seen.put(nums[i], i);
    }
    return new int[]{};
}"""

SOL = {
    "hook": "Two numbers, one target. Can you find them without checking every single pair?",
    "summary": "Given a list of numbers and a target, return the indices of the two numbers that add up to it.",
    "problem_say": "We get a list of numbers and a target. We need the positions of two numbers that add up to it. "
                   "For two, seven, eleven, fifteen and a target of nine, the answer is zero and one.",
    "intuition": "For every number, the partner we need is already decided: target minus that number.",
    "intuition_say": "Here's the trick. Once you pick a number, its partner is fixed. It's just the target minus that number. "
                     "So really we're searching, not adding.",
    "approaches": [
        {"name": "Brute Force", "idea": "Try every pair of numbers until one adds up to the target.",
         "idea_say": "The obvious way is to check every pair. Pick a number, then try every number after it.",
         "time": "O(n^2)", "space": "O(1)", "code": BRUTE, "java_code": BRUTE_JAVA,
         "steps": [
             {"lines": [2, 3], "say": "We grab the length, then start the outer loop at index zero.", "watch": ["n", "i"]},
             {"lines": [4, 6], "say": "The inner loop pairs index zero with index one. Two plus seven, is that nine? Yes!",
              "watch": ["i", "j"]},
             {"lines": [7, 7], "say": "That matches our target, so we return the indices zero and one.", "watch": ["i", "j"]}],
         "complexity_say": "Two nested loops means O of n squared time, but only constant extra space."},
        {"name": "Hash Map", "idea": "Remember numbers we've seen; look up each number's partner instantly.",
         "idea_say": "Instead of searching for the partner, let's remember what we've already seen in a dictionary.",
         "time": "O(n)", "space": "O(n)", "code": HASH, "java_code": HASH_JAVA,
         "steps": [
             {"lines": [2, 2], "say": "We start with an empty map. It tracks elements with their indices.", "watch": ["seen"]},
             {"lines": [3, 4], "say": "First number is two, so the partner we need is seven.", "watch": ["i", "x", "need"]},
             {"lines": [5, 7], "say": "Seven isn't in the map yet, so we store two at index zero and move on.",
              "watch": ["seen"]},
             {"lines": [3, 4], "say": "Next number is seven, and the partner we need is two.", "watch": ["i", "x", "need"]},
             {"lines": [5, 6], "say": "Two is in the map! We return its index, zero, and the current index, one.",
              "watch": ["seen", "i"]}],
         "complexity_say": "One pass, and map lookups are constant time, so O of n time and O of n space."},
    ],
    "comparison_say": "Brute force is simple but slow. The hash map trades a little memory for a big speed-up.",
    "outro_say": "That's Two Sum. Try tomorrow's problem before I post it, and subscribe so you don't miss it.",
    "tests": [[[2, 7, 11, 15], 9], [[3, 2, 4], 6], [[3, 3], 6], [[1, 5, 9, 14], 23], [[-1, -2, -3, -4, -5], -8]],
}

if __name__ == "__main__":
    results = verifier.verify(SOL)
    print("Verified OK:", {k: v[:2] for k, v in results.items()})
    work = config.DATA / PROBLEM["slug"]
    work.mkdir(parents=True, exist_ok=True)
    meta = {"title": "LeetCode 1: Two Sum - Stop Using Brute Force", "thumb_text": "STOP BRUTE FORCE",
            "thumb_sub": "ALL APPROACHES", "palette": {"bg1": "#1b1464", "bg2": "#0f7bff", "accent": "#ffd400"},
            "hashtags": ["leetcode", "twosum", "dsa", "coding", "interviewprep"], "tags": ["leetcode", "two sum"],
            "hook_line": "Two Sum explained with a brute force and a hash map approach."}

    # Use Java code for the thumbnail
    thumb_code = SOL["approaches"][-1].get("java_code", SOL["approaches"][-1]["code"])
    thumbnail.make(PROBLEM, meta, thumb_code, work / "thumb.jpg")

    beats = scenes.build_beats(PROBLEM, SOL, results)
    video, chapters = render.build_video(beats, PROBLEM, work, seed=1)
    meta["description"] = metadata.build_description(PROBLEM, SOL, meta, chapters)
    (work / "metadata.json").write_text(json.dumps(meta, indent=2))
    print("\nVideo:", video, "\nThumbnail:", work / "thumb.jpg", "\nChapters:\n" + "\n".join(chapters))