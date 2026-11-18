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

    raise VerifyError(
        "Python code must define solution(), a top-level function, "
        "or a public method inside class Solution."
    )


HARNESS = r"""
import json, sys, copy

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
    if not arr:
        return None
    head = ListNode(arr[0])
    cur = head
    for value in arr[1:]:
        cur.next = ListNode(value)
        cur = cur.next
    return head

def linked_to_list(node):
    out = []
    seen = set()
    while node:
        if id(node) in seen:
            raise ValueError("cycle detected while converting linked-list output")
        seen.add(id(node))
        out.append(node.val)
        node = node.next
    return out

def list_to_tree(arr):
    if not arr or arr[0] is None:
        return None
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
    if not root:
        return []
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

def convert_linked_argument(value, source):
    # Convert either ListNode input or ListNode[] input without flattening it.
    if not isinstance(value, list):
        return value

    # LeetCode #23: the argument is a list of linked lists.
    # Preserve the outer list and convert each inner list to its own ListNode.
    if value and all(item is None or isinstance(item, list) for item in value):
        return [
            list_to_linked(item) if isinstance(item, list) else None
            for item in value
        ]

    # [] is ambiguous between an empty ListNode and an empty ListNode[];
    # for mergeKLists it represents an empty collection of linked lists.
    compact_source = source.replace("_", "").lower()
    if not value and "mergeklists" in compact_source:
        return []

    # Ordinary LeetCode linked-list argument, e.g. reverseList([1, 2, 3]).
    return list_to_linked(value)

code, tests = json.load(sys.stdin)
ns = {
    "ListNode": ListNode,
    "TreeNode": TreeNode,
    "list_to_linked": list_to_linked,
    "linked_to_list": linked_to_list,
    "list_to_tree": list_to_tree,
    "tree_to_list": tree_to_list,
}
exec(code, ns)
f = ns["solution"]

# Detect whether generated code uses linked-list or tree nodes.
src = code.lower()
uses_linked = "listnode" in src or "linked" in src or ".next" in src
uses_tree = "treenode" in src

results = []
for test_args in tests:
    converted = []
    for arg in copy.deepcopy(test_args):
        if isinstance(arg, list) and uses_linked:
            converted.append(convert_linked_argument(arg, src))
        elif isinstance(arg, list) and uses_tree:
            converted.append(list_to_tree(arg))
        else:
            converted.append(arg)

    result = f(*converted)
    if hasattr(result, "next"):
        result = linked_to_list(result)
    elif hasattr(result, "left") or hasattr(result, "right"):
        result = tree_to_list(result)
    results.append(result)

print(json.dumps(results))
"""


TRACE_HARNESS = r"""
import json, sys, copy

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
    if not arr:
        return None
    head = ListNode(arr[0])
    cur = head
    for value in arr[1:]:
        cur.next = ListNode(value)
        cur = cur.next
    return head

def list_to_tree(arr):
    if not arr or arr[0] is None:
        return None
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

def convert_linked_argument(value, source):
    if not isinstance(value, list):
        return value
    if value and all(item is None or isinstance(item, list) for item in value):
        return [
            list_to_linked(item) if isinstance(item, list) else None
            for item in value
        ]
    compact_source = source.replace("_", "").lower()
    if not value and "mergeklists" in compact_source:
        return []
    return list_to_linked(value)

code, args = json.load(sys.stdin)
events = []

def local(frame, event, arg):
    if event == "line" and len(events) < 4000:
        events.append([
            frame.f_lineno,
            {
                key: repr(value)[:60]
                for key, value in frame.f_locals.items()
                if not key.startswith(("__", "."))
            },
        ])
    return local

def glob(frame, event, arg):
    return local if frame.f_code.co_filename == "<sol>" else None

ns = {"ListNode": ListNode, "TreeNode": TreeNode}
exec(compile(code, "<sol>", "exec"), ns)
f = ns["solution"]
src = code.lower()
uses_linked = "listnode" in src or "linked" in src or ".next" in src
uses_tree = "treenode" in src

converted = []
for value in copy.deepcopy(args):
    if isinstance(value, list) and uses_linked:
        converted.append(convert_linked_argument(value, src))
    elif isinstance(value, list) and uses_tree:
        converted.append(list_to_tree(value))
    else:
        converted.append(value)

sys.settrace(glob)
try:
    f(*converted)
finally:
    sys.settrace(None)

print(json.dumps(events))
"""


def _run(harness: str, payload, timeout: int = 20):
    try:
        process = subprocess.run(
            [sys.executable, "-c", harness],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise VerifyError("code execution timed out") from exc

    if process.returncode != 0:
        raise VerifyError(process.stderr[-1000:])

    try:
        return json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        raise VerifyError(
            f"Verifier harness returned invalid JSON: {process.stdout[-500:]}"
        ) from exc


def trace(code: str, args: list) -> list:
    try:
        adapted_code = _ensure_solution_entrypoint(code)
        return _run(TRACE_HARNESS, [adapted_code, args])
    except Exception:
        return []


def normalize_sol(sol: dict) -> dict:
    """Unwrap nested dictionary containers if the LLM wrapped the JSON."""
    if not isinstance(sol, dict):
        raise VerifyError("Response is not a valid JSON object")

    if "approaches" not in sol:
        for value in sol.values():
            if isinstance(value, dict) and "approaches" in value:
                return value
    return sol


def _check_shape(sol: dict) -> None:
    required_fields = (
        "hook", "summary", "problem_say", "intuition",
        "intuition_say", "comparison_say", "outro_say",
    )
    for key in required_fields:
        if not str(sol.get(key, "")).strip():
            raise VerifyError(f"missing field '{key}'")

    approaches = sol.get("approaches")
    tests = sol.get("tests")
    if not isinstance(approaches, list) or not approaches:
        raise VerifyError("missing approaches")
    if not isinstance(tests, list) or not tests:
        raise VerifyError("missing tests")

    if not isinstance(tests[0], (list, tuple)):
        sol["tests"] = [tests]

    for approach in approaches:
        for key in (
            "name", "idea", "idea_say", "time", "space",
            "code", "complexity_say", "steps",
        ):
            if not approach.get(key):
                raise VerifyError(f"approach missing '{key}'")
        if not approach.get("java_code"):
            raise VerifyError(f"{approach['name']}: missing 'java_code'")

        python_lines = len(approach["code"].splitlines())
        java_lines = len(approach["java_code"].splitlines())
        if python_lines > 22:
            raise VerifyError(
                f"{approach['name']}: python code has {python_lines} lines, max is 22"
            )
        if java_lines > 24:
            raise VerifyError(
                f"{approach['name']}: java_code has {java_lines} lines, max is 24"
            )

        for step in approach["steps"]:
            raw_lines = step.get("lines", [1, 1])
            if isinstance(raw_lines, (int, float)):
                lo = hi = int(raw_lines)
            elif isinstance(raw_lines, (list, tuple)):
                if not raw_lines:
                    lo = hi = 1
                elif len(raw_lines) == 1:
                    lo = hi = int(raw_lines[0])
                else:
                    lo, hi = int(raw_lines[0]), int(raw_lines[-1])
            else:
                lo = hi = 1

            if lo > hi:
                lo, hi = hi, lo
            step["lines"] = [lo, hi]

            if not (1 <= lo <= max(python_lines, java_lines) + 2):
                raise VerifyError(
                    f"{approach['name']}: invalid step line range {step['lines']}"
                )
            if not str(step.get("say", "")).strip():
                raise VerifyError(f"{approach['name']}: step is missing 'say'")


def verify(sol: dict) -> dict:
    """Run all approaches against the same tests and compare their outputs."""
    _check_shape(sol)
    results = {}

    for approach in sol["approaches"]:
        try:
            adapted_code = _ensure_solution_entrypoint(approach["code"])
            results[approach["name"]] = _run(
                HARNESS, [adapted_code, sol["tests"]]
            )
        except VerifyError as exc:
            raise VerifyError(f"{approach['name']}: {exc}") from exc

    names = list(results)
    for name in names[1:]:
        if results[name] != results[names[0]]:
            raise VerifyError(
                f"'{name}' disagrees with '{names[0]}' on some test"
            )
    return results
