"""Generate, verify, and cache problem-specific LeetCode solutions and narration."""
import ast
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
            "- ALWAYS write 'hee' instead of 'hi' for the Hindi particle. Never write 'hi' for emphasis. "
            "- ALWAYS write 'toh' instead of 'to'. "
            "- ALWAYS write 'doh' instead of 'do' when referring to the number 2. "
            "- ALWAYS write 'istemaal' instead of 'use' when the English word means using something. "
            "- ALWAYS write 'isse' instead of 'ise' and 'huye' instead of 'hue'. "
            "- NEVER start a sentence with 'Hee!' — use 'Hey!' or 'Arey!' instead. "
            "The on-screen fields ('summary', 'intuition', 'idea') and all displayed code MUST remain in clean ENGLISH. "
            "For linked-list/tree problems, use standard LeetCode ListNode/TreeNode Java signatures; Python tests "
            "must use JSON-compatible lists and the verifier converts those lists internally. "
            "Follow the problem's real function signature; do not assume every problem has the same arguments. "
            "Reply with ONLY valid JSON, no markdown fences or introductory text."
        )
    return (
        "You are an energetic, witty senior software engineer coaching candidates "
        "through technical coding interviews on YouTube. Explain concepts with clear intuition, "
        "conversational banter, and practical engineering trade-offs. Never sound like a textbook "
        "and never recite code line-by-line. "
        "The problem's actual function signature is authoritative: do not assume fixed argument names, "
        "argument count, or data types. For linked-list/tree problems, use standard LeetCode Java "
        "ListNode/TreeNode signatures and JSON-compatible list tests for the Python verifier. "
        "Reply with ONLY valid JSON, no markdown fences or introductory text."
    )


# Intentionally generic: do not give the model a Two Sum implementation or its test cases as a template.
PROMPT = """LeetCode problem #{id}: {title} ({difficulty})
Topics: {topics}

Problem statement:
{content}

Target video length: 7-8 minutes. Spoken sections should be educational and include a concrete dry run
using an example that belongs to THIS problem. On-screen explanations and code must be in English.

Return exactly one valid JSON object with this schema. Replace every placeholder with content specific to
THIS LeetCode problem. Do not copy an algorithm, function signature, variable names, or test cases from any
other problem.
{{
  "hook": "30-40 word curiosity-driven opening",
  "summary": "clean on-screen problem summary in English, at most 30 words",
  "problem_say": "80-110 words explaining this problem and one of its examples",
  "intuition": "core technical insight for on-screen display in English, at most 25 words",
  "intuition_say": "90-120 words explaining the breakthrough and why it works",
  "approaches": [
    {{
      "name": "a meaningful approach name appropriate for THIS problem",
      "idea": "on-screen approach summary in English, at most 25 words",
      "idea_say": "70-90 words explaining this approach and its trade-offs",
      "time": "correct time complexity, such as O(n)",
      "space": "correct auxiliary-space complexity, such as O(1)",
      "code": "Complete executable Python implementation with the correct function signature, escaped newlines",
      "java_code": "Complete LeetCode-compatible Java implementation with escaped newlines",
      "steps": [
        {{
          "lines": [1, 2],
          "say": "55-75 words explaining this code step with a problem-specific dry run",
          "watch": ["real variable names used by this implementation"]
        }}
      ],
      "complexity_say": "65-85 words accurately explaining this approach's complexity"
    }}
  ],
  "comparison_say": "80-100 words comparing the approaches and interview trade-offs",
  "outro_say": "50-70 word sign-off with a relevant edge case and invitation to comment",
  "tests": []
}}

MANDATORY CORRECTNESS RULES:
1. Provide at least two genuinely different approaches when the problem supports them. All approaches must solve
   THIS problem, accept the same inputs, and return equivalent output formats.
2. Every Python implementation must be complete and executable; preferably define a top-level function named
   solution with the exact number and types of parameters required by THIS problem. Do not leave ellipses/placeholders.
3. The 'tests' field MUST contain 3-5 test cases. Never leave it empty.
4. Each test case is a LIST of positional arguments for ONE call to the Python function. The outer list is the
   collection of test cases; the inner list contains that test's arguments.
5. Determine the argument count and types from THIS problem statement and the Python function signature. Every test
   must match exactly. A one-string-argument problem has cases shaped like [["first string"], ["second string"]].
   A multi-argument problem has each case containing every required argument, in order.
6. Use examples from THIS problem statement first, then add valid edge cases. Never reuse unrelated example inputs.
   Tests must be valid JSON values and must actually be accepted by the generated function.
7. For linked-list/tree problems, represent input structures as JSON-compatible lists. Do not put Python objects in tests.
8. Every step must contain 'lines': [start, end] as a two-integer list, and a non-empty 'say' string. Line ranges should
   refer to the Python implementation's real line numbers; keep the Java implementation reasonably aligned.
9. On-screen text and code must remain English. If the selected narration language is Hindi/Hinglish, only spoken
   narration fields must use conversational Hinglish and follow the phonetic rules.
10. Output only the complete JSON object. No markdown fences, comments, or explanation outside JSON.
"""


def _selected_entrypoint(code: str):
    """Return (AST function node, is_instance_method) for the function verifier will call."""
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise verifier.VerifyError(f"Python solution has invalid syntax: {exc}") from exc

    top_functions = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    for node in top_functions:
        if node.name == "solution":
            return node, False

    cls = next(
        (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Solution"),
        None,
    )
    if cls is not None:
        methods = [
            node for node in cls.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_")
        ]
        if methods:
            called_methods = set()
            for method in methods:
                for child in ast.walk(method):
                    if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
                        called_methods.add(child.func.attr)
            candidates = [method for method in methods if method.name not in called_methods]
            target = (candidates or methods)[-1]
            decorators = {
                dec.id if isinstance(dec, ast.Name) else dec.attr
                for dec in target.decorator_list
                if isinstance(dec, (ast.Name, ast.Attribute))
            }
            return target, "staticmethod" not in decorators

    functions = [node for node in top_functions if not node.name.startswith("_")]
    if functions:
        called_functions = set()
        for function in functions:
            for child in ast.walk(function):
                if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
                    called_functions.add(child.func.id)
        candidates = [function for function in functions if function.name not in called_functions]
        return (candidates or functions)[-1], False

    raise verifier.VerifyError(
        "Python code must define solution(), a public method in class Solution, or a top-level function."
    )


def _validate_tests_against_signatures(sol: dict) -> None:
    """Fail early with useful feedback if any generated test passes the wrong number of arguments."""
    tests = sol.get("tests")
    if not isinstance(tests, list) or not tests:
        raise verifier.VerifyError("'tests' must be a non-empty list of test cases.")

    # Normalize the unambiguous shorthand where the model returned one argument-list, not a list of cases.
    # Mixed shapes like [[array], target] are intentionally rejected as ambiguous.
    if all(not isinstance(test, (list, tuple)) for test in tests):
        tests = [tests]
        sol["tests"] = tests
    elif any(not isinstance(test, (list, tuple)) for test in tests):
        raise verifier.VerifyError(
            "Malformed 'tests': every test case must be a list of positional arguments; "
            "do not mix a test's arguments with separate test cases."
        )

    if not 3 <= len(tests) <= 5:
        raise verifier.VerifyError(
            f"Expected 3-5 test cases for this problem, got {len(tests)}."
        )

    for approach in sol.get("approaches", []):
        code = approach.get("code", "")
        fn, is_instance_method = _selected_entrypoint(code)
        positional = list(fn.args.posonlyargs) + list(fn.args.args)
        if is_instance_method and positional and positional[0].arg in ("self", "cls"):
            positional = positional[1:]
        required = len(positional) - len(fn.args.defaults)
        max_positional = None if fn.args.vararg is not None else len(positional)

        for index, case in enumerate(tests, 1):
            count = len(case)
            if count < required or (max_positional is not None and count > max_positional):
                expected = (
                    str(required) if max_positional == required
                    else f"{required} to {max_positional if max_positional is not None else 'many'}"
                )
                raise verifier.VerifyError(
                    f"{approach.get('name', 'Approach')}: tests[{index}] supplies {count} positional "
                    f"argument(s), but Python entry point accepts {expected}. Each test must be a list of "
                    "arguments for one call to THIS problem's solution. Fix the test data and ensure every "
                    "approach uses the same problem-specific signature."
                )


def generate_verified(problem: dict, work_dir: Path | None = None, attempts: int = 3) -> tuple[dict, dict]:
    # 1. Check local cache first; stale or invalid caches are regenerated.
    cache_file = (work_dir / "solution.json") if work_dir else None
    if cache_file and cache_file.exists():
        try:
            print(f"✓ Found cached solution at {cache_file.name}. Verifying it...")
            sol = json.loads(cache_file.read_text(encoding="utf-8"))
            sol = verifier.normalize_sol(sol)
            _validate_tests_against_signatures(sol)
            results = verifier.verify(sol)
            return sol, results
        except Exception as exc:
            print(f"[Info] Cache invalid ({exc}). Regenerating with Gemini...")

    system_prompt = get_system_prompt()
    base = PROMPT.format(
        id=problem["id"],
        title=problem["title"],
        difficulty=problem["difficulty"],
        topics=", ".join(problem["topics"]),
        content=problem["content"],
        channel_name=config.CHANNEL_NAME,
    )
    feedback = ""
    for attempt in range(1, attempts + 1):
        try:
            print(f"Sending prompt to Gemini (Attempt {attempt}/{attempts})...", flush=True)
            sol = llm.ask_json(system_prompt, base + feedback)
            sol = verifier.normalize_sol(sol)
            _validate_tests_against_signatures(sol)
            results = verifier.verify(sol)
            print(f"✓ Solutions verified on attempt {attempt}!")

            if cache_file:
                cache_file.write_text(json.dumps(sol, indent=2, ensure_ascii=False), encoding="utf-8")
                print(f"✓ Solution cached to {cache_file.name}")
            return sol, results

        except (verifier.VerifyError, ValueError, KeyError, TypeError, SyntaxError) as exc:
            print(f"Attempt {attempt} failed: {exc}", flush=True)
            feedback = (
                f"\n\nCRITICAL VERIFICATION FAILURE: {exc}\n"
                "Return a complete corrected JSON object. Do not repeat the previous tests or implementation. "
                "Inspect the actual Python function signature in EACH approach. 'tests' must contain 3-5 cases, "
                "each case being a list of positional arguments for exactly one call. The number and types of "
                "arguments in every case must match the function. Use examples and edge cases for the current "
                "LeetCode problem only; do not copy sample data or function signatures from another problem. "
                "All approaches must use the same signature and return equivalent results. "
                "Keep each step's 'lines' a two-integer [start, end] list. Return only valid JSON."
            )

    raise RuntimeError(f"Could not produce verified solutions after {attempts} attempts")
