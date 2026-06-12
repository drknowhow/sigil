"""Canonicalization of host (Python) ASTs into hashable plain data.

Canonical form rules, applied in order (sigil-canonical-hashing skill):
1. Formatting/comments never reach us (ast.parse drops them); docstrings are
   stripped here (leading string-constant Expr; empty body -> Pass).
2. Position info is excluded structurally: ``ast.iter_fields`` yields _fields
   only, and lineno/col/end_* live in _attributes.
3. Constants hash by parsed value (0x10 == 16), via typed repr. No folding.
4. No alpha-renaming (D-003): names are part of identity.

Output shape: ``[NodeClassName, [[field, value], ...]]`` — tagged lists only,
so the structure is CBOR/JSON-safe and order-deterministic by construction.
"""

from __future__ import annotations

import ast
from typing import Any

# Fields derived from comments or irrelevant to semantics.
_SKIP_FIELDS = {"type_comment", "type_ignores"}

_DOC_BEARING = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def _strip_docstring(body: list[ast.stmt]) -> list[ast.stmt]:
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]
    return body or [ast.Pass()]


def canon_node(node: ast.AST) -> list:
    if isinstance(node, ast.Constant):
        v = node.value
        return ["Constant", type(v).__name__, repr(v)]
    out_fields: list[list] = []
    for name, value in ast.iter_fields(node):
        if name in _SKIP_FIELDS:
            continue
        if name == "body" and isinstance(node, _DOC_BEARING):
            value = _strip_docstring(value)
        out_fields.append([name, _canon_value(value)])
    return [type(node).__name__, out_fields]


def _canon_value(v: Any) -> Any:
    if isinstance(v, ast.AST):
        return canon_node(v)
    if isinstance(v, list):
        return [_canon_value(x) for x in v]
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    # Defensive: anything exotic becomes a typed repr rather than failing.
    return ["py", type(v).__name__, repr(v)]


def canonical_fn(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> list:
    """Canonical data for one function definition."""
    return canon_node(fn)


def canonical_module(tree: ast.Module) -> list:
    """Canonical data for a whole parsed module."""
    return canon_node(tree)


# ---- inverse: canonical data -> Python AST -> source (for harness expand) ----


def uncanon(data):  # noqa: ANN001 — recursive plain-data input
    """Rebuild a Python AST node from canonical data. Inverse of canon_node
    up to stripped trivia (docstrings/positions are gone by design)."""
    if isinstance(data, list):
        if len(data) == 3 and data[0] == "Constant":
            text = data[2]
            value = ... if text == "Ellipsis" else ast.literal_eval(text)
            return ast.Constant(value=value)
        if (
            len(data) == 2
            and isinstance(data[0], str)
            and hasattr(ast, data[0])
            and isinstance(data[1], list)
            and all(isinstance(p, list) and len(p) == 2 for p in data[1])
        ):
            cls = getattr(ast, data[0])
            kwargs = {name: _unvalue(v) for name, v in data[1]}
            # restore fields canon strips (semantics-free) with neutral values
            for missing in set(getattr(cls, "_fields", ())) - kwargs.keys():
                kwargs[missing] = [] if missing == "type_ignores" else None
            return cls(**kwargs)
        return [_unvalue(x) for x in data]
    return data


def _unvalue(v):  # noqa: ANN001
    if isinstance(v, list):
        out = uncanon(v)
        return out
    return v


def host_source(data) -> str:  # noqa: ANN001
    """Canonical host data -> runnable source text (deterministic projection)."""
    node = uncanon(data)
    return ast.unparse(ast.fix_missing_locations(node))
