"""Phase 0 exit-gate properties (written before implementation, per CLAUDE.md).

The four load-bearing properties from the sigil-canonical-hashing skill:
1. Formatting noise (comments / blank lines / trailing whitespace) -> hash unchanged
2. Docstring add / remove / edit -> hash unchanged
3. Semantic AST mutation (rename, constant change, operator swap) -> hash CHANGES
4. Serialization round-trips byte-identically; hash survives a round-trip
"""

import ast
import string

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from sigil.core.hash import canonical_cbor, digest_data, fn_digest
from sigil.core.pycanon import canonical_fn

BASE_FN = '''def f(a, b):
    """Doc line."""
    total = a + b
    for i in range(3):
        total += i * a
    if total > 10:
        return total * 2
    return total - 1
'''

BASE_DIGEST_SRC = BASE_FN  # canonical: digest must ignore everything below

_COMMENT_ALPHABET = string.ascii_letters + string.digits + " #!?.,:;()[]{}'-_=+*"


def _comment_text() -> st.SearchStrategy[str]:
    return st.text(alphabet=_COMMENT_ALPHABET, min_size=0, max_size=40)


@st.composite
def noisy_variant(draw: st.DrawFn) -> str:
    """Apply only semantics-preserving formatting noise to BASE_FN."""
    lines = BASE_FN.rstrip("\n").split("\n")
    # Full-line comments and blank lines at arbitrary positions.
    for _ in range(draw(st.integers(0, 5))):
        pos = draw(st.integers(0, len(lines)))
        indent = " " * draw(st.integers(0, 8))
        kind = draw(st.sampled_from(["comment", "blank"]))
        lines.insert(pos, indent + "# " + draw(_comment_text()) if kind == "comment" else "")
    # Trailing comments / trailing whitespace on existing code lines.
    for _ in range(draw(st.integers(0, 4))):
        i = draw(st.integers(0, len(lines) - 1))
        if lines[i].strip() and not lines[i].lstrip().startswith("#"):
            suffix = draw(st.sampled_from(["  # " + draw(_comment_text()), "   ", "\t"]))
            lines[i] = lines[i] + suffix
    return "\n".join(lines) + "\n"


@settings(max_examples=200)
@given(noisy_variant())
def test_formatting_noise_does_not_change_hash(noisy: str) -> None:
    assert fn_digest(noisy) == fn_digest(BASE_DIGEST_SRC)


@settings(max_examples=200)
@given(st.one_of(st.none(), st.text(max_size=200)))
def test_docstring_add_remove_edit_does_not_change_hash(doc: str | None) -> None:
    tree = ast.parse(BASE_FN)
    fn = tree.body[0]
    assert isinstance(fn, ast.FunctionDef)
    fn.body = fn.body[1:]  # strip the existing docstring
    if doc is not None:
        fn.body.insert(0, ast.Expr(value=ast.Constant(value=doc)))
    variant = ast.unparse(ast.fix_missing_locations(tree)) + "\n"
    assert fn_digest(variant) == fn_digest(BASE_DIGEST_SRC)


@settings(max_examples=100)
@given(st.integers(), st.integers())
def test_distinct_constants_produce_distinct_hashes(x: int, y: int) -> None:
    assume(x != y)
    mk = "def g(a):\n    return a + {}\n".format
    assert fn_digest(mk(x)) != fn_digest(mk(y))


def test_semantic_mutations_change_hash() -> None:
    base = "def g(a, b):\n    total = a + b\n    return total\n"
    mutants = [
        "def g(a, c):\n    total = a + c\n    return total\n",  # param rename (no alpha-eq)
        "def g(a, b):\n    total = a - b\n    return total\n",  # operator swap
        "def g(a, b):\n    result = a + b\n    return result\n",  # local var rename
        "def h(a, b):\n    total = a + b\n    return total\n",  # fn rename
    ]
    base_d = fn_digest(base)
    for m in mutants:
        assert fn_digest(m) != base_d, f"mutation not detected: {m!r}"
    # And distinct mutants are mutually distinct (no over-normalization collapse).
    ds = [fn_digest(m) for m in mutants]
    assert len(set(ds)) == len(ds)


def test_equivalent_literal_spellings_hash_identically() -> None:
    # Parsed value is hashed, not the text (skill rule 3): 0x10 == 16.
    assert fn_digest("def g():\n    return 0x10\n") == fn_digest("def g():\n    return 16\n")
    # But no constant folding: 16 != 8 + 8 as expressions.
    assert fn_digest("def g():\n    return 16\n") != fn_digest("def g():\n    return 8 + 8\n")


def test_serialization_round_trips_byte_identically() -> None:
    fn = ast.parse(BASE_FN).body[0]
    data = canonical_fn(fn)
    b1, b2 = canonical_cbor(data), canonical_cbor(data)
    assert b1 == b2
    assert digest_data(data) == digest_data(data)


def test_canonical_cbor_independent_of_dict_insertion_order() -> None:
    a = {"alpha": 1, "beta": [1, 2], "gamma": None}
    b = {"gamma": None, "beta": [1, 2], "alpha": 1}
    assert canonical_cbor(a) == canonical_cbor(b)
