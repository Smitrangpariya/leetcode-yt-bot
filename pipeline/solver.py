import json
from pathlib import Path
from . import llm, verifier
import config

def get_system_prompt() -> str:
    if config.LANGUAGE.lower() in ("hi", "hindi"):
        return (
            "You are an energetic, witty senior software engineer coaching candidates "
            "through technical coding interviews on YouTube. "
            "IMPORTANT HINGLISH PHONETIC RULES FOR SPOKEN FIELDS: "
            "Spoken narration fields ('hook', 'problem_say', 'intuition_say', 'idea_say', "
            "'steps.say', 'complexity_say', 'comparison_say', 'outro_say') MUST be written in "
            "conversational Hinglish. "
            "To prevent text-to-speech mispronouncing words: "
            "- ALWAYS write 'hee' instead of 'hi' (e.g. 'brute force hee strike karta hai'). Never write 'hi' for emphasis. "
            "- ALWAYS write 'toh' instead of 'to' (e.g. 'toh chaliye shuru karte hain'). "
            "- ALWAYS write 'doh' instead of 'do' when referring to the number 2 (e.g. 'doh nested loops'). "
            "- ALWAYS write 'istemaal' instead of 'use' (e.g. 'hash map ka istemaal karenge'). "
            "- ALWAYS write 'isse' instead of 'ise' and 'huye' instead of 'hue'. "
            "- NEVER start any sentence with 'Hee!' — use 'Hey!' or 'Arey!' instead. "
            "LINKED LIST / TREE PROBLEMS: "
            "For problems involving ListNode or TreeNode, your Python 'code' and 'tests' MUST use plain Python lists "
            "(e.g. [2,4,3] for a linked list, or [1,null,3] for a tree). "
            "The pipeline will auto-convert lists to/from ListNode/TreeNode internally. "
            "Your 'java_code' MUST use standard LeetCode ListNode/TreeNode class signatures. "
            "On-screen fields ('summary', 'intuition', 'idea') and code MUST remain in clean ENGLISH. "
            "Reply with ONLY valid JSON, no markdown fences."
        )
    return (
        "You are an energetic, witty senior software engineer coaching candidates "
        "through technical coding interviews on YouTube. You explain concepts with crystal-clear intuition, "
        "conversational banter, and practical engineering trade-offs. You never sound like a textbook, "
        "and you never recite code line-by-line. "
        "LINKED LIST / TREE PROBLEMS: "
        "For problems involving ListNode or TreeNode, your Python 'code' and 'tests' MUST use plain Python lists "
        "(e.g. [2,4,3] for a linked list, or [1,null,3] for a tree). "
        "The pipeline will auto-convert lists to/from ListNode/TreeNode internally. "
        "Your 'java_code' MUST use standard LeetCode ListNode/TreeNode class signatures. "
        "Reply with ONLY valid JSON, no markdown fences or introductory text."
    )

PROMPT = """LeetCode problem #{id}: {title} ({difficulty})
Topics: {topics}

{content}

Target Video Length: 7 to 8 minutes.
Every spoken section must be rich, thorough, and highly educational with concrete array dry-runs.

Return JSON with exactly this shape:
{{
  "hook": "sharp, curiosity-driven cold open, 30-40 words",
  "summary": "clean on-screen problem summary in English, <=30 words",
  "problem_say": "in-depth problem breakdown walking through sample test input and zero-based indexing, 80-110 words",
  "intuition": "core technical breakthrough for on-screen display in English, <=25 words",
  "intuition_say": "deep dive into why naive approaches fail and the aha moment for picking the optimal data structure, 90-120 words",
  "approaches": [
    {{
      "name": "Brute Force",
      "idea": "on-screen approach summary in English, <=25 words",
      "idea_say": "explaining the naive strategy and why it causes time limits, 70-90 words",
      "time": "O(n^2)",
      "space": "O(1)",
      "code": "def solution(nums, target):\\n    ...",
      "java_code": "public int[] twoSum(int[] nums, int target) {{\\n    ...\\n}}",
      "steps": [
        {{
          "lines": [2, 3],
          "say": "detailed explanation of nested loop variables with dry run on test numbers, 55-75 words",
          "watch": ["i", "j"]
        }},
        {{
          "lines": [4, 6],
          "say": "detailed explanation of condition check and return logic, 55-75 words",
          "watch": ["i", "j"]
        }}
      ],
      "complexity_say": "thorough Big-O analysis explaining why comparisons grow quadratically, 65-85 words"
    }},
    {{
      "name": "Optimal (One-Pass Hash Map)",
      "idea": "on-screen optimal summary in English, <=25 words",
      "idea_say": "explaining the transition to hash map and why trading memory achieves linear time, 70-90 words",
      "time": "O(n)",
      "space": "O(n)",
      "code": "def solution(nums, target):\\n    ...",
      "java_code": "public int[] twoSum(int[] nums, int target) {{\\n    ...\\n}}",
      "steps": [
        {{
          "lines": [2, 2],
          "say": "explaining data structure initialization and memory allocation, 45-65 words",
          "watch": ["numMap"]
        }},
        {{
          "lines": [3, 4],
          "say": "explaining complement calculation with specific number arithmetic, 55-75 words",
          "watch": ["i", "complement"]
        }},
        {{
          "lines": [5, 7],
          "say": "explaining map lookup check and solution packaging, 55-75 words",
          "watch": ["complement", "numMap"]
        }},
        {{
          "lines": [8, 8],
          "say": "explaining fallback map insertion for future elements, 55-75 words",
          "watch": ["numMap"]
        }}
      ],
      "complexity_say": "comprehensive Big-O time and space trade-off analysis, 65-85 words"
    }}
  ],
  "comparison_say": "deep side-by-side comparison advising interview strategy, 80-100 words",
  "outro_say": "charismatic sign-off proposing an edge case for viewers in comments and teasing tomorrow's problem, 50-70 words",
  "tests": []
}}


CRITICAL RULES:
1. Every step must have 'lines': [start, end] as a 2-element integer list.
2. In Hinglish spoken fields, write 'hee' instead of 'hi', 'toh' instead of 'to', 'doh' instead of 'do', and 'istemaal' instead of 'use'.
3. The 'tests' field MUST contain 3-5 valid test cases. Never return an empty list.
4. Each test case must be a list of positional arguments for ONE call to the Python solution.
5. Inspect the CURRENT LeetCode problem and the generated Python function signature. Every test must match the correct number and types of arguments.
6. NEVER copy Two Sum test cases into another problem unless the current problem is Two Sum.
7. For a one-argument string problem such as longest substring, use this format:
   "tests": [["abcabcbb"], ["bbbbb"], ["pwwkew"]]
8. For a one-argument array problem, wrap the complete array as the single argument:
   "tests": [[[1, 2, 3]], [[4, 5, 6]]]
9. For a two-argument problem such as Two Sum, each test case must contain both arguments:
   "tests": [[[2, 7, 11, 15], 9], [[3, 2, 4], 6]]
10. Return only valid JSON. Replace all examples with appropriate test cases for the CURRENT problem.
"""


def generate_verified(problem: dict, work_dir: Path | None = None, attempts: int = 3) -> tuple[dict, dict]:
    # 1. Check local cache first
    cache_file = (work_dir / "solution.json") if work_dir else None
    if cache_file and cache_file.exists():
        try:
            print(f"✓ Found cached solution at {cache_file.name}. Skipping LLM API call!")
            sol = json.loads(cache_file.read_text(encoding="utf-8"))
            results = verifier.verify(sol)
            return sol, results
        except Exception as e:
            print(f"[Info] Cache invalid ({e}). Regenerating with Gemini...")

    system_prompt = get_system_prompt()
    base = PROMPT.format(
        id=problem["id"],
        title=problem["title"],
        difficulty=problem["difficulty"],
        topics=", ".join(problem["topics"]),
        content=problem["content"],
        channel_name=config.CHANNEL_NAME
    )
    feedback = ""
    for i in range(attempts):
        try:
            print(f"Sending prompt to Gemini (Attempt {i + 1}/{attempts})...", flush=True)
            sol = llm.ask_json(system_prompt, base + feedback)
            sol = verifier.normalize_sol(sol)
            results = verifier.verify(sol)
            print(f"✓ Solutions verified on attempt {i + 1}!")

            # Save solution to cache for future renders
            if cache_file:
                cache_file.write_text(json.dumps(sol, indent=2), encoding="utf-8")
                print(f"✓ Solution cached to {cache_file.name}")

            return sol, results
        except (verifier.VerifyError, ValueError, KeyError, TypeError) as e:
            print(f"Attempt {i + 1} failed: {e}")
            feedback = (
                f"\n\nCRITICAL FIX: Your previous answer failed verification with: '{e}'.\n"
                "Return the COMPLETE JSON object with all fields and 2-element [start, end] lines array."
            )
    raise RuntimeError("Could not produce verified solutions")
