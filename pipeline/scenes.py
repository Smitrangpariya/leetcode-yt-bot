"""Turns the verified solution into a timeline of 'beats'.
A beat = one frame spec + (optional) narration line. Silent beats have a fixed duration.
Code walkthroughs: displays Java code, lines reveal one by one, then a highlight moves through the code in sync
with the narration while a side panel shows REAL variable values from an execution trace.
"""
import ast
import json
import re
from . import verifier


def _fmt_args(code: str, args: list) -> str:
    try:
        fn = next(n for n in ast.parse(code).body if isinstance(n, ast.FunctionDef))
        names = [a.arg for a in fn.args.args]
    except Exception:
        names = [f"arg{i + 1}" for i in range(len(args))]
    s = ", ".join(f"{n} = {json.dumps(v)}" for n, v in zip(names, args))
    return s if len(s) <= 78 else s[:75] + "..."


def _array_visual(problem: dict, args: list, output) -> dict | None:
    """Build an array diagram from a simple list input and verified output."""
    if not args or not isinstance(args[0], list):
        return None

    values = args[0]
    if not values or len(values) > 14:
        return None
    if any(isinstance(value, (list, dict)) for value in values):
        return None

    highlights = []
    is_two_sum = "two sum" in str(problem.get("title", "")).lower()
    if (
        is_two_sum
        and isinstance(output, (list, tuple))
        and len(output) == 2
        and all(type(index) is int and 0 <= index < len(values) for index in output)
    ):
        highlights = list(output)

    return {"values": values, "highlight_indices": highlights}


def _get_line_bounds(step: dict) -> tuple[int, int]:
    """Safely extracts (lo, hi) line bounds from step dict."""
    lines = step.get("lines", [1, 1])
    if isinstance(lines, (int, float)):
        return int(lines), int(lines)
    if isinstance(lines, (list, tuple)):
        if len(lines) == 0:
            return 1, 1
        if len(lines) == 1:
            return int(lines[0]), int(lines[0])
        return int(lines[0]), int(lines[-1])
    return 1, 1


def _watch_for_steps(events: list, steps: list) -> list[dict]:
    """For each step find the real execution moment and return matching variables."""
    out, cursor = [], 0
    last_good = {}  # carry forward last non-empty watch state
    for s in steps:
        lo, hi = _get_line_bounds(s)
        found = next((j for j in range(cursor, len(events)) if lo <= events[j][0] <= hi), None)
        if found is None:
            found = next((j for j in range(len(events)) if lo <= events[j][0] <= hi), None)
        if found is None:
            # Carry forward last known state instead of empty dict
            out.append(dict(last_good) if last_good else {})
            continue
        after = next((j for j in range(found + 1, len(events)) if not (lo <= events[j][0] <= hi)), found)
        cursor = found + 1
        state = events[after][1]

        # Case-insensitive and snake_case fallback lookup
        matched_vars = {}
        for var in s.get("watch", []):
            if var in state:
                matched_vars[var] = state[var]
            else:
                # Convert camelCase to snake_case (e.g. numMap -> num_map)
                snake = re.sub(r'(?<!^)(?=[A-Z])', '_', var).lower()
                if snake in state:
                    matched_vars[var] = state[snake]
                elif var.lower() in state:
                    matched_vars[var] = state[var.lower()]

        if matched_vars:
            last_good = matched_vars
        elif last_good:
            # Carry forward last non-empty state to avoid flashing
            matched_vars = dict(last_good)
        out.append(matched_vars)
    return out


def build_beats(problem: dict, sol: dict, results: dict) -> list[dict]:
    beats: list[dict] = []
    first = sol["approaches"][0]
    last = sol["approaches"][-1]
    demo_args = sol["tests"][0]
    demo_output = results[first["name"]][0]
    demo_out = json.dumps(demo_output)
    array_demo = _array_visual(problem, demo_args, demo_output)
    topics = ", ".join(problem["topics"][:3])

    beats.append({
        "spec": {"layout": "title", "title": problem["title"], "topics": topics},
        "say": sol["hook"],
        "chapter": "Intro",
    })

    problem_spec = {
        "layout": "text",
        "heading": "The Problem",
        "paras": [sol["summary"]],
        "example": [
            ("Input", _fmt_args(first["code"], demo_args)),
            ("Output", demo_out if len(demo_out) < 70 else demo_out[:67] + "..."),
        ],
    }
    if array_demo:
        problem_spec["array_visual"] = array_demo
    beats.append({
        "spec": problem_spec,
        "say": sol["problem_say"],
        "chapter": "The problem",
    })

    beats.append({
        "spec": {
            "layout": "text",
            "heading": "The Key Idea",
            "paras": [sol["intuition"]],
            "cards": [
                {
                    "label": first["name"],
                    "value": first.get("time", "—"),
                    "detail": first.get("idea", ""),
                },
                {
                    "label": last["name"],
                    "value": last.get("time", "—"),
                    "detail": last.get("idea", ""),
                },
            ],
        },
        "say": sol["intuition_say"],
        "chapter": "Intuition",
    })

    total = len(sol["approaches"])
    for ai, approach in enumerate(sol["approaches"], 1):
        head = f"Approach {ai}/{total}: {approach['name']}"
        beats.append({
            "spec": {
                "layout": "text",
                "heading": head,
                "paras": [approach["idea"]],
                "cards": [
                    {
                        "label": "TIME COMPLEXITY",
                        "value": approach.get("time", "—"),
                        "detail": "How runtime grows as the input gets larger.",
                    },
                    {
                        "label": "SPACE COMPLEXITY",
                        "value": approach.get("space", "—"),
                        "detail": "Additional memory used by this approach.",
                    },
                    {
                        "label": "CORE STRATEGY",
                        "value": approach["name"],
                        "detail": approach.get("idea", ""),
                    },
                ],
            },
            "say": approach["idea_say"],
            "chapter": f"Approach {ai}: {approach['name']}",
        })

        # Use Java code for the video display slides.
        display_code = approach.get("java_code") or approach["code"]
        n = len(display_code.splitlines())
        per = max(0.05, min(0.14, 2.2 / n))

        # Code reveals line by line.
        for k in range(1, n + 1):
            beats.append({
                "spec": {
                    "layout": "code",
                    "heading": head,
                    "code": display_code,
                    "visible": k,
                    "mode": "writing",
                },
                "dur": per,
            })

        # Trace live variables using the Python execution harness.
        events = verifier.trace(approach["code"], demo_args)
        watches = _watch_for_steps(events, approach["steps"])

        # Step walkthrough with highlighted lines.
        for si, (step, watch) in enumerate(zip(approach["steps"], watches), 1):
            lo, hi = _get_line_bounds(step)
            beats.append({
                "spec": {
                    "layout": "code",
                    "heading": head,
                    "code": display_code,
                    "active": (lo, hi),
                    "mode": "step",
                    "step": (si, len(approach["steps"])),
                    "watch": watch,
                },
                "say": step["say"],
            })

        beats.append({
            "spec": {
                "layout": "code",
                "heading": head,
                "code": display_code,
                "mode": "done",
                "time": approach["time"],
                "space": approach["space"],
            },
            "say": approach["complexity_say"],
        })

    beats.append({
        "spec": {
            "layout": "table",
            "heading": "Side by Side",
            "rows": [(a["name"], a["time"], a["space"]) for a in sol["approaches"]],
        },
        "say": sol["comparison_say"],
        "chapter": "Comparison",
    })
    beats.append({
        "spec": {"layout": "outro"},
        "say": sol["outro_say"],
        "chapter": "Wrap-up",
    })
    return beats
