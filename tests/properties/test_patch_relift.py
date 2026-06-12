"""Property (plan section 7): patch application == re-lift equivalence —
patching the canonical form to match an edit produces the same digest as
re-lifting the edited source."""

import ast

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from sigil.core.hash import digest_data
from sigil.core.patch import apply_ops
from sigil.core.pycanon import canonical_fn


def _canon(src: str) -> list:
    return canonical_fn(ast.parse(src).body[0])


@settings(max_examples=100)
@given(st.integers(0, 10**6), st.integers(0, 10**6))
def test_patch_equals_relift_for_constant_edits(a: int, b: int) -> None:
    assume(a != b)
    base = _canon(f"def g():\n    return {a}\n")
    edited = _canon(f"def g():\n    return {b}\n")
    # the Constant lives at body.0.value; its repr is element 2 of the triple
    patched = apply_ops(base, [{"path": "body.0.value.2", "op": "replace", "value": str(b)}])
    assert digest_data(patched) == digest_data(edited)
    assert digest_data(patched) != digest_data(base)
