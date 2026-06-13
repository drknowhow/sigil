"""AST patches against canonical data (spec mechanism 2: edits as patches).

Paths address into a node's plain-data form (to_data output): dict keys,
list indices, and canonical host-AST field names ([ClassName, [[field,
value], ...]] from core.pycanon). Untouched subtrees are untouched by
construction — output tokens scale with the change, not the file.
"""

from __future__ import annotations

import copy
from typing import Any

OPS = {"replace", "insert", "delete"}


class PatchError(ValueError):
    """Malformed patch op; message has cause + remedy, .code is machine-parseable."""

    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code


def _is_canon_node(v: Any) -> bool:
    return (
        isinstance(v, list)
        and len(v) == 2
        and isinstance(v[0], str)
        and isinstance(v[1], list)
        and all(isinstance(p, list) and len(p) == 2 and isinstance(p[0], str) for p in v[1])
    )


def _step(container: Any, token: str) -> tuple[Any, Any]:
    """Resolve one path token -> (parent_container, key/index). Raises KeyError."""
    if isinstance(container, dict):
        if token not in container:
            raise KeyError(token)
        return container, token
    if _is_canon_node(container) and not token.isdigit():
        for pair in container[1]:
            if pair[0] == token:
                return pair, 1  # the field's value slot
        raise KeyError(token)
    if isinstance(container, list):
        if not token.lstrip("-").isdigit():
            raise KeyError(token)
        i = int(token)
        if not -len(container) <= i < len(container) + 1:  # +1 allows append-insert
            raise KeyError(token)
        return container, i
    raise KeyError(token)


def apply_ops(data: Any, ops: list[dict]) -> Any:
    """Apply patch ops to a deep copy of ``data``; returns the new data."""
    out = copy.deepcopy(data)
    for idx, op in enumerate(ops):
        kind = op.get("op")
        path = op.get("path", "")
        if kind not in OPS:
            raise PatchError(
                f"op #{idx}: unknown op {kind!r}. Remedy: use one of {sorted(OPS)}.", code="bad_op"
            )
        if not isinstance(path, str) or not path:
            raise PatchError(
                f"op #{idx}: missing or empty 'path'. Remedy: give a dotted path "
                "into the canonical form (expand the hash to see it).",
                code="bad_path",
            )
        tokens = path.split(".")
        node = out
        try:
            for token in tokens[:-1]:
                parent, key = _step(node, token)
                node = parent[key]
            parent, key = _step(node, tokens[-1])
        except KeyError as exc:
            raise PatchError(
                f"op #{idx}: path {path!r} fails at token {exc.args[0]!r}. "
                "Remedy: expand the target hash and use its field names / list "
                "indices; paths address the canonical data form.",
                code="bad_path",
            ) from exc
        if kind == "replace":
            parent[key] = copy.deepcopy(op.get("value"))
        elif kind == "insert":
            if not isinstance(parent, list) or not isinstance(key, int):
                raise PatchError(
                    f"op #{idx}: insert needs a list index path, got {path!r}. "
                    "Remedy: point at the list position to insert before.",
                    code="bad_path",
                )
            parent.insert(key, copy.deepcopy(op.get("value")))
        else:  # delete
            if isinstance(parent, list) and isinstance(key, int) or isinstance(parent, dict):
                del parent[key]
            else:
                raise PatchError(
                    f"op #{idx}: cannot delete a canonical field slot at {path!r}. "
                    "Remedy: replace its value instead.",
                    code="bad_path",
                )
    return out


def diff_data(old: Any, new: Any, _path: str = "") -> list[dict]:
    """Minimal patch ops turning ``old`` into ``new`` (patch-by-snippet, v1.1).
    Untouched subtrees produce no ops, by construction."""
    if old == new:
        return []
    if (
        isinstance(old, dict)
        and isinstance(new, dict)
        and old.get("kind") == new.get("kind")
        and set(old) == set(new)
    ):
        ops: list[dict] = []
        for k in sorted(old):
            ops += diff_data(old[k], new[k], f"{_path}.{k}" if _path else k)
        return ops
    if isinstance(old, list) and isinstance(new, list) and len(old) == len(new):
        ops = []
        for i, (a, b) in enumerate(zip(old, new, strict=True)):
            ops += diff_data(a, b, f"{_path}.{i}" if _path else str(i))
        return ops
    if not _path:
        raise PatchError(
            "Snippet replaces the entire definition (kind or shape changed at the "
            "root). Remedy: keep the same definition kind and name; for wholesale "
            "rewrites, load a new definition instead of patching.",
            code="bad_op",
        )
    return [{"path": _path, "op": "replace", "value": copy.deepcopy(new)}]
