"""Content addressing: canonical CBOR + sha256.

- Encoding: cbor2 ``canonical=True`` — definite lengths, deterministically
  sorted map keys (decisions.md D-004).
- Display: '#' + first 4 hex chars; a store escalates to 8 on prefix
  collision, stickily (DigestNamer). The full hash is what is persisted;
  short form is display-only.
"""

from __future__ import annotations

import ast as pyast
import hashlib
from typing import Any

import cbor2

from sigil.core.ast import Node, to_data
from sigil.core.ir import lower_fn

SHORT_LEN = 4
ESCALATED_LEN = 8


def canonical_cbor(data: Any) -> bytes:
    return cbor2.dumps(data, canonical=True)


def digest_data(data: Any) -> str:
    """Full sha256 hex digest of canonical CBOR bytes."""
    return hashlib.sha256(canonical_cbor(data)).hexdigest()


def digest_node(node: Node) -> str:
    return digest_data(to_data(node))


def short(full: str, n: int = SHORT_LEN) -> str:
    return "#" + full[:n]


def fn_digest(source: str) -> str:
    """Digest of the first function definition in ``source`` (test/PoC helper)."""
    tree = pyast.parse(source)
    for stmt in pyast.walk(tree):
        if isinstance(stmt, (pyast.FunctionDef, pyast.AsyncFunctionDef)):
            return digest_data(lower_fn(stmt))
    raise ValueError(
        "No function definition found in source. Remedy: pass source containing at least one 'def'."
    )


class DigestNamer:
    """Store-level short-name allocator with sticky 4 -> 8 char escalation."""

    def __init__(self) -> None:
        self.length = SHORT_LEN
        self._by_prefix: dict[str, str] = {}

    def display(self, full: str) -> str:
        prefix = full[:SHORT_LEN]
        known = self._by_prefix.get(prefix)
        if known is not None and known != full:
            self.length = ESCALATED_LEN  # sticky, store-wide
        self._by_prefix[prefix] = full
        return short(full, self.length)
