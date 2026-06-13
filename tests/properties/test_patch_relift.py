"""Property (plan section 7): patch application == re-lift equivalence —
patching the canonical form to match an edit produces the same digest as
re-lifting the edited source."""

import ast

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from sigil.core.hash import digest_data
from sigil.core.ir import lower_fn
from sigil.core.patch import apply_ops


def _canon(src: str) -> list:
    return lower_fn(ast.parse(src).body[0])


@settings(max_examples=100)
@given(st.integers(0, 10**6), st.integers(0, 10**6))
def test_patch_equals_relift_for_constant_edits(a: int, b: int) -> None:
    assume(a != b)
    base = _canon(f"def g():\n    return {a}\n")
    edited = _canon(f"def g():\n    return {b}\n")
    # IR: ["def", name, args, body, ...]; body stmt 0 = ["ret", ["const", t, repr]]
    patched = apply_ops(base, [{"path": "3.0.1.2", "op": "replace", "value": str(b)}])
    assert digest_data(patched) == digest_data(edited)
    assert digest_data(patched) != digest_data(base)
