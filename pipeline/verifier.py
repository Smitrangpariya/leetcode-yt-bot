"""Differential testing + an execution tracer with robust schema normalization."""
import ast
import json
import subprocess
import sys


class VerifyError(Exception):
    pass


def _ensure_solution_entrypoint(code: str) -> str:
    """Adapt common LeetCode Python signatures to the verifier's solution() API."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        # Leave invalid code untouched so the normal verifier reports its syntax error.
        return code

    if any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "solution"
        for node in tree.body
    ):
        return code

    # Prefer a LeetCode-style `class Solution` and its main public method.
    solution_class = next(
        (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Solution"),
        None,
    )
    if solution_class is not None:
        methods = [
            node for node in solution_class.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not node.name.startswith("_")
        ]
        if methods:
            called_by_other_method = set()
            for method in methods:
                for node in ast.walk(method):
                    if (
                        isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and node.func.attr != method.name
                    ):
                        called_by_other_method.add(node.func.attr)

            candidates = [m for m in methods if m.name not in called_by_other_method]
            target = (candidates or methods)[-1]
            return (
                code.rstrip()
                + "\n\n# Adapter for the pipeline verifier\n"
                + "def solution(*args, **kwargs):\n"
                + f"    return Solution().{target.name}(*args, **kwargs)\n"
            )

    # Otherwise, adapt a top-level function whose name is not solution().
    functions = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    ]
    if functions:
        called_by_other_function = set()
        for function in functions:
            for node in ast.walk(function):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id != function.name
                ):
                    called_by_other_function.add(node.func.id)

        candidates = [f for f in functions if f.name not in called_by_other_function]
        target = (candidates or functions)[-1]
        return (
            code.rstrip()
            + "\n\n# Adapter for the pipeline verifier\n"
            + "def solution(*args, **kwargs):\n"
            + f"    return {target.name}(*args, **kwargs)\n"
        )

    # Do not silently invent an implementation if the model returned an unsupported shape.
    raise VerifyError(
        "Python code must define solution(), a top-level function, "
        "or a public method inside class Solution."
    )


HARNESS = """
import json, sys, copy, inspect

class ListNode:
    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next

class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right

def list_to_linked(arr):
    if not arr: return None
    head = ListNode(arr[0])
    cur = head
    for v in arr[1:]:
        cur.next = ListNode(v)
        cur = cur.next
    return head

def linked_to_list(node):
    out = []
    while node:
        out.append(node.val)
        node = node.next
    return out

def list_to_tree(arr):
    if not arr or arr[0] is None: return None
    root = TreeNode(arr[0])
    q, i = [root], 1
    while q and i < len(arr):
        node = q.pop(0)
        if i < len(arr) and arr[i] is not None:
            node.left = TreeNode(arr[i])
            q.append(node.left)
        i += 1
        if i < len(arr) and arr[i] is not None:
            node.right = TreeNode(arr[i])
            q.append(node.right)
        i += 1
    return root

def tree_to_list(root):
    if not root: return []
    out, q = [], [root]
    while q:
        node = q.pop(0)
        if node:
            out.append(node.val)
            q.extend([node.left, node.right])
        else:
            out.append(None)
    while out and out[-1] is None:
        out.pop()
    return out

code, tests = json.load(sys.stdin)
ns = {"ListNode": ListNode, "TreeNode": TreeNode,
      "list_to_linked": list_to_linked, "linked_to_list": linked_to_list,
      "list_to_tree": list_to_tree, "tree_to_list": tree_to_list}
exec(code, ns)
f = ns["solution"]

# Detect if function uses ListNode/TreeNode via source inspection
src = code.lower()
uses_linked = "listnode" in src or "linked" in src or ".next" in src
uses_tree = "treenode" in src

results = []
for args in tests:
    converted = []
    for a in copy.deepcopy(args):
        if isinstance(a, list) and uses_linked:
            converted.append(list_to_linked(a))
        elif isinstance(a, list) and uses_tree:
            converted.append(list_to_tree(a))
        else:
            converted.append(a)
    result = f(*converted)
    if hasattr(result, 'next'):
        result = linked_to_list(result)
    elif hasattr(result, 'left') or hasattr(result, 'right'):
        result = tree_to_list(result)
    results.append(result)
print(json.dumps(results))
"""

TRACE_HARNESS = """
import json, sys, copy
code, args = json.load(sys.stdin)
events = []
def local(frame, event, arg):
    if event == "line" and len(events) < 4000:
        events.append([frame.f_lineno, {k: repr(v)[:60] for k, v in frame.f_locals.items()
                                         if not k.startswith(("__", "."))}])
    return local
def glob(frame, event, arg):
    return local if frame.f_code.co_filename == "<sol>" else None
ns = {}
exec(compile(code, "<sol>", "exec"), ns)
f = ns["solution"]
sys.settrace(glob)
try:
    f(*copy.deepcopy(args))
finally:
    sys.settrace(None)
print(json.dumps(events))
"""


def _run(harness: str, payload, timeout: int = 20):
    try:
        p = subprocess.run(
            [sys.executable, "-c", harness],
            input=json.dumps(payload), capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise VerifyError("code execution timed out")
    if p.returncode != 0:
        raise VerifyError(p.stderr[-600:])
    return json.loads(p.stdout)


def trace(code: str, args: list) -> list:
    try:
        adapted_code = _ensure_solution_entrypoint(code)
        return _run(TRACE_HARNESS, [adapted_code, args])
    except Exception:
        return []


def normalize_sol(sol: dict) -> dict:
    """Unwrap nested dictionary containers if LLM wrapped the JSON."""
    if not isinstance(sol, dict):
        raise VerifyError("Response is not a valid JSON object")

    if "approaches" not in sol:
        for val in sol.values():
            if isinstance(val, dict) and "approaches" in val:
                return val
    return sol


def _check_shape(sol: dict) -> None:
    for k in ("hook", "summary", "problem_say", "intuition", "intuition_say", "comparison_say", "outro_say"):
        if not str(sol.get(k, "")).strip():
            raise VerifyError(f"missing field '{k}'")

    approaches = sol.get("approaches")
    tests = sol.get("tests")
    if not approaches or not tests:
        raise VerifyError("missing approaches or tests")

    if isinstance(tests, list) and len(tests) > 0:
        if not isinstance(tests[0], (list, tuple)):
            sol["tests"] = [tests]

    for a in approaches:
        for k in ("name", "idea", "idea_say", "time", "space", "code", "complexity_say", "steps"):
            if not a.get(k):
                raise VerifyError(f"approach missing '{k}'")
        if not a.get("java_code"):
            raise VerifyError(f"{a['name']}: missing 'java_code'")

        n = len(a["code"].splitlines())
        if n > 22:
            raise VerifyError(f"{a['name']}: python code has {n} lines, max is 22")
        jn = len(a["java_code"].splitlines())
        if jn > 24:
            raise VerifyError(f"{a['name']}: java_code has {jn} lines, max is 24")

        for s in a["steps"]:
            raw_lines = s.get("lines", [1, 1])
            if isinstance(raw_lines, (int, float)):
                lo = hi = int(raw_lines)
            elif isinstance(raw_lines, (list, tuple)):
                if len(raw_lines) == 0:
                    lo = hi = 1
                elif len(raw_lines) == 1:
                    lo = hi = int(raw_lines[0])
                else:
                    lo = int(raw_lines[0])
                    hi = int(raw_lines[-1])
            else:
                lo = hi = 1

            if lo > hi:
                lo, hi = hi, lo

            s["lines"] = [lo, hi]
            if not (1 <= lo <= max(n, jn) + 2) or not str(s.get("say", "")).strip():
                raise VerifyError(f"{a['name']}: bad step {s}")


def verify(sol: dict) -> dict:
    """Raises VerifyError on any problem. Returns {approach_name: [outputs per test]}."""
    _check_shape(sol)
    results = {}
    for a in sol["approaches"]:
        try:
            adapted_code = _ensure_solution_entrypoint(a["code"])
            results[a["name"]] = _run(HARNESS, [adapted_code, sol["tests"]])
        except VerifyError as e:
            raise VerifyError(f"{a['name']}: {e}")
    names = list(results)
    for n in names[1:]:
        if results[n] != results[names[0]]:
            raise VerifyError(f"'{n}' disagrees with '{names[0]}' on some test")
    return results
