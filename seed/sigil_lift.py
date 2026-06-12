#!/usr/bin/env python3
"""sigil_lift.py — proof-of-concept Tier-1/Tier-2 lifter: Python -> Sigil digest sheet.

Mechanical only: parsing, canonicalization, content-addressing, heuristic effect
inference. No LLM, no contracts (that's Tier 3). Usage:

    python sigil_lift.py <file.py> [more.py ...]
"""

import ast
import hashlib
import sys

# ---- Tier 2: effect rules (import-rooted heuristics; over-approximate) ----
EFFECT_ROOTS = {
    "requests": "!net", "urllib": "!net", "httpx": "!net", "socket": "!net",
    "aiohttp": "!net",
    "open": "!fs", "pathlib": "!fs", "shutil": "!fs", "tempfile": "!fs",
    "os": "!env",          # refined below for os.environ vs os.path
    "random": "!rand", "secrets": "!rand",
    "time": "!clock", "datetime": "!clock",
    "print": "!io", "input": "!io", "logging": "!io",
    "subprocess": "!unsafe", "eval": "!unsafe", "exec": "!unsafe",
}


def _call_root(node: ast.Call) -> str | None:
    """Leftmost name of a call: requests.get(...) -> 'requests', open(...) -> 'open'."""
    f = node.func
    while isinstance(f, ast.Attribute):
        f = f.value
    return f.id if isinstance(f, ast.Name) else None


def infer_effects(fn: ast.FunctionDef) -> list[str]:
    fx: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            root = _call_root(node)
            if root in EFFECT_ROOTS:
                fx.add(EFFECT_ROOTS[root])
            elif root is None:
                fx.add("!unsafe?")          # dynamic dispatch we can't see through
        elif isinstance(node, ast.Global):
            fx.add("!mut")                   # writes global state
    return sorted(fx) if fx else ["pure?"]   # '?' — static guess, not proof


# ---- Tier 1: canonicalization + content addressing ----
def canonicalize(fn: ast.FunctionDef) -> str:
    """Strip docstrings and dump structure only — formatting/comments never reach us."""
    fn = ast.parse(ast.unparse(fn)).body[0]   # detach a clean copy
    if (fn.body and isinstance(fn.body[0], ast.Expr)
            and isinstance(fn.body[0].value, ast.Constant)
            and isinstance(fn.body[0].value.value, str)):
        fn.body = fn.body[1:] or [ast.Pass()]
    return ast.dump(fn, annotate_fields=False, include_attributes=False)


def digest(fn: ast.FunctionDef) -> str:
    return hashlib.sha256(canonicalize(fn).encode()).hexdigest()[:4]


def signature(fn: ast.FunctionDef) -> str:
    args = ",".join(
        a.arg + (f" {ast.unparse(a.annotation)}" if a.annotation else "")
        for a in fn.args.args
    )
    ret = f" -> {ast.unparse(fn.returns)}" if fn.returns else " -> ?"
    return f"({args}){ret}"


def est_tokens(text: str) -> int:
    return max(1, len(text) // 4)            # rough GPT-style chars/4 heuristic


# ---- driver ----
def lift(path: str) -> None:
    src = open(path).read()
    tree = ast.parse(src)
    fns = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    if not fns:
        print(f"; {path}: no functions found")
        return

    print(f"; digest sheet — {path}  (Tier 1+2 mechanical lift)")
    sheet_lines = []
    for fn in fns:
        line = f"#{digest(fn)} {fn.name}{signature(fn)} {' '.join(infer_effects(fn))}"
        sheet_lines.append(line)
        print(line)

    full, sheet = est_tokens(src), est_tokens("\n".join(sheet_lines))
    print(f"; context cost: full source ≈{full} tok · digest sheet ≈{sheet} tok "
          f"· {full / sheet:.0f}× smaller")
    print("; '?' marks static guesses — Tier 2 over-approximates, never trusts.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for p in sys.argv[1:]:
        lift(p)
        print()
