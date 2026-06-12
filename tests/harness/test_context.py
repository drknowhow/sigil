"""R1 — append-only session context (sigil-harness-rules skill).

The load-bearing property: for ANY sequence of ops, sheet history is
prefix-stable — every earlier render is a byte prefix of every later one.
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from sigil.harness.context import SessionSheet

op_st = st.one_of(
    st.tuples(st.just("append"), st.text(alphabet="abc#-> 0123456789", min_size=1, max_size=20)),
    st.tuples(
        st.just("supersede"),
        st.text(alphabet="0123456789abcdef", min_size=8, max_size=8),
        st.text(alphabet="0123456789abcdef", min_size=8, max_size=8),
        st.text(alphabet="abc()", min_size=0, max_size=8),
    ),
    st.tuples(st.just("expand"), st.text(alphabet="0123456789abcdef", min_size=4, max_size=8)),
)


@settings(max_examples=200)
@given(st.lists(op_st, max_size=30))
def test_sheet_history_is_prefix_stable(ops) -> None:
    sheet = SessionSheet()
    renders = [sheet.render()]
    for op in ops:
        if op[0] == "append":
            sheet.append(op[1])
        elif op[0] == "supersede":
            sheet.supersede(op[1], op[2], op[3])
        else:
            sheet.log_expand(op[1])
        renders.append(sheet.render())
    for earlier, later in zip(renders, renders[1:], strict=False):
        assert later.startswith(earlier), "R1 violated: sheet rewrote history"


def test_supersede_appends_and_keeps_old_line() -> None:
    sheet = SessionSheet()
    sheet.append("#aaaa fn1() pure?")
    sheet.supersede("aaaa1111", "bbbb2222", "fn1()")
    text = sheet.render()
    assert "#aaaa fn1() pure?" in text  # the old line stays
    assert "#aaaa1111 -> #bbbb2222 fn1()" in text


def test_stats_track_appends_and_expansions() -> None:
    sheet = SessionSheet()
    sheet.append("x")
    sheet.log_expand("aaaa")
    sheet.log_expand("aaaa")
    s = sheet.stats()
    assert s["lines"] == 1 and s["expansions"] == 2
