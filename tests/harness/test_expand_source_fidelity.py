"""Muninn Part 1: expand(form="source") must return what the author wrote.

The de-commented IR projection throws away the docstring (the function's
intent, in the author's words) and every comment. For a human<->AI tool that
is the most important thing on the page. Fix: the store keeps the original
source bytes alongside the canonical object (keyed by the same hash); expand
returns them verbatim for lifted, unpatched fns, and a clearly-labeled
projection for fns that exist only as a patched AST.

See docs/decisions.md D-043.
"""

from __future__ import annotations

from sigil.harness.core import Harness

PROBE = '''# a leading comment explaining intent
def fetch_prices(tickers, start, end):
    """Fetch prices for tickers between start and end.

    Multi-line docstring with detail the author cared about.
    """
    result = {}          # inline comment, idiosyncratic spacing
    for t in tickers:
        result[t] = _get(t, start, end)
    return result
'''

PROJECTED_LABEL = "projected from canonical form"


def _lift_probe(tmp_path) -> tuple[Harness, str]:
    src = tmp_path / "probe.py"
    src.write_text(PROBE, encoding="utf-8")
    h = Harness(tmp_path)
    h.lift(str(src))
    return h, h.lifted_fns()["fetch_prices"]


def test_expand_source_preserves_docstring_and_comments(tmp_path) -> None:
    h, ref = _lift_probe(tmp_path)
    out = h.expand(ref, form="source")
    # the entire docstring survives, verbatim
    assert "Multi-line docstring with detail the author cared about." in out
    assert '"""Fetch prices for tickers between start and end.' in out
    # inline + leading comments survive
    assert "# inline comment, idiosyncratic spacing" in out
    assert "# a leading comment explaining intent" in out
    # an unpatched, lifted fn is original source, never a labeled projection
    assert PROJECTED_LABEL not in out


def test_expand_source_is_byte_identical_per_hash(tmp_path) -> None:
    # R2: expand is byte-identical for the same hash, forever.
    h, ref = _lift_probe(tmp_path)
    a = h.expand(ref, form="source")
    b = h.expand("#" + ref[:8], form="source")
    assert a == b


def test_patched_fn_expands_to_labeled_projection(tmp_path) -> None:
    h, ref = _lift_probe(tmp_path)
    # patch into a new AST that has no original-source record
    new = h.patch_snippet(
        ref,
        "def fetch_prices(tickers, start, end):\n"
        "    result = {}\n"
        "    for t in tickers:\n"
        "        result[t] = _get(t, start, end) * 2\n"
        "    return result\n",
    )
    proj = h.expand(new["new_hash"], form="source")
    # the patched edit is visible
    assert "* 2" in proj
    # ...but it is honestly labeled as a projection, not original text
    assert PROJECTED_LABEL in proj
    # and the comment markers cannot be passed off as the author's
    assert "# a leading comment explaining intent" not in proj
