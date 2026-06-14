"""Phase 2 gate properties (failing first, per sigil-transpile-verify skill):

print(parse(text)) == text   for canonical text
parse(print(ast))  == ast    always
"""

import string

from hypothesis import given, settings
from hypothesis import strategies as st

from sigil.core import expr as E
from sigil.core.ast import Effect, EffectRow, Fn, Import, Module, Param, TypeExpr
from sigil.lang.parser import parse_module
from sigil.lang.printer import glyph_output, print_module

# ---------------------------------------------------------------- canonical
CANONICAL = [
    """module demo

use requests

fn add(a Int, b Int) -> Int
  pure
{
  ret a + b
}
""",
    """module spec

goal fetch_prices {
  intent: "Daily OHLCV for given tickers"
  in: tickers [Str], range DateRange
  out: Frame
  fx: !fs(./cache) !net(alpaca.markets)
  law: "rate <= 200/min"
  verify:
    out.rows.complete_for(tickers, range)
    out.no_nulls(o, h, l, c)
}

fn dedupe(xs [T]) -> [T]
  pure
  post |r| r.set == xs.set and r.len <= xs.len
{
  s := {}
  ret [x | x <- xs, s.insert(x)]
}
""",
    """module ctrl

fn classify(n Int) -> Str
  pure
  pre n >= 0
{
  if n == 0 {
    ret "zero"
  } else {
    ret "many"
  }
}

fn total(xs [Int]) -> Int
{
  acc := 0
  for x <- xs {
    acc := acc + x
  }
  ret acc
}
""",
    """module lits

fn mix(m Map) -> Map
{
  s := {1, 2}
  e := {}
  d := {:}
  d["k"] := s
  ret d
}
""",
]


def test_canonical_sources_round_trip_exactly() -> None:
    for src in CANONICAL:
        assert print_module(parse_module(src)) == src


def test_ascii_is_canonical_and_glyphs_parse_equal() -> None:
    # ASCII is the canonical printed form (D-044): each operator is one token,
    # where the glyph spelling costs two. Glyphs stay accepted on input.
    glyph = "module m\n\nfn f(a Int, b Int) -> Bool\n  pure\n{\n  ret a ≤ b ∧ ¬b ∨ a ≠ b\n}\n"
    ascii_ = (
        "module m\n\nfn f(a Int, b Int) -> Bool\n  pure\n{\n  ret a <= b and not b or a != b\n}\n"
    )
    assert parse_module(glyph) == parse_module(ascii_)
    assert print_module(parse_module(glyph)) == ascii_  # printer emits ASCII
    with glyph_output():
        assert print_module(parse_module(ascii_)) == glyph  # glyphs remain opt-in


# ------------------------------------------------------------- generated ASTs
RESERVED = {
    "module",
    "use",
    "goal",
    "fn",
    "pre",
    "post",
    "ret",
    "if",
    "else",
    "for",
    "while",
    "pure",
    "true",
    "false",
    "none",
    "in",
    "and",
    "or",
    "not",
    "intent",
    "out",
    "fx",
    "law",
    "verify",
    "ack",
}
name_st = st.from_regex(r"[a-z][a-z0-9_]{0,5}", fullmatch=True).filter(lambda s: s not in RESERVED)
str_st = st.text(alphabet=string.ascii_letters + ' _.,!?"\\\n\t', max_size=10)


def lit_st() -> st.SearchStrategy:
    return st.one_of(
        st.integers(0, 10**6).map(lambda i: E.ELit(lit="int", val=str(i))),
        st.tuples(st.integers(0, 99), st.integers(0, 99)).map(
            lambda t: E.ELit(lit="float", val=f"{t[0]}.{t[1]}")
        ),
        st.sampled_from(["true", "false"]).map(lambda v: E.ELit(lit="bool", val=v)),
        st.just(E.ELit(lit="none", val="none")),
        str_st.map(lambda s: E.ELit(lit="str", val=s)),
    )


BINOPS = ["or", "and", "==", "!=", "<", "<=", ">", ">=", "in", "+", "-", "*", "/", "//", "%", "**"]

expr_st = st.deferred(
    lambda: st.one_of(
        lit_st(),
        name_st.map(lambda n: E.EName(id=n)),
        st.builds(E.EAttr, value=expr_st, attr=name_st),
        st.builds(E.ECall, func=expr_st, args=st.lists(expr_st, max_size=2)),
        st.builds(E.EIndex, value=expr_st, index=expr_st),
        st.builds(E.EBin, op=st.sampled_from(BINOPS), left=expr_st, right=expr_st),
        st.builds(E.EUn, op=st.sampled_from(["not", "-"]), value=expr_st),
        st.builds(E.EList, items=st.lists(expr_st, max_size=3)),
        st.builds(E.ESet, items=st.lists(expr_st, min_size=1, max_size=3)),
        st.builds(
            E.EMap, items=st.lists(st.builds(E.EPair, key=expr_st, value=expr_st), max_size=2)
        ),
        st.builds(
            E.EComp, elt=expr_st, var=name_st, iter=expr_st, guards=st.lists(expr_st, max_size=2)
        ),
    )
)

lvalue_st = st.one_of(
    name_st.map(lambda n: E.EName(id=n)),
    st.builds(E.EAttr, value=name_st.map(lambda n: E.EName(id=n)), attr=name_st),
    st.builds(E.EIndex, value=name_st.map(lambda n: E.EName(id=n)), index=expr_st),
)

stmt_st = st.deferred(
    lambda: st.one_of(
        st.builds(E.SAssign, target=lvalue_st, value=expr_st),
        st.builds(E.SRet, value=st.one_of(st.none(), expr_st)),
        st.builds(E.SExpr, value=expr_st),
        st.builds(
            E.SIf,
            cond=expr_st,
            then=st.lists(stmt_st, min_size=1, max_size=2),
            orelse=st.lists(stmt_st, max_size=2),
        ),
        st.builds(
            E.SFor, var=name_st, iter=expr_st, body=st.lists(stmt_st, min_size=1, max_size=2)
        ),
        st.builds(E.SWhile, cond=expr_st, body=st.lists(stmt_st, min_size=1, max_size=2)),
    )
)

type_st = st.deferred(
    lambda: st.one_of(
        st.sampled_from(["Str", "Int", "F64", "Bool", "Map"]).map(lambda n: TypeExpr(name=n)),
        type_st.map(lambda t: TypeExpr(name="[]", args=[t])),
    )
)

EFFECTS = ["clock", "env", "fs", "io", "mut", "net", "rand", "unsafe"]
fx_st = st.one_of(
    st.just(EffectRow(effects=[], uncertain=False)),  # declared pure
    st.lists(st.sampled_from(EFFECTS), min_size=1, max_size=3, unique=True).map(
        lambda ns: EffectRow(
            effects=[Effect(name=n, scope=None, uncertain=False) for n in sorted(ns)],
            uncertain=False,
        )
    ),
)

fn_st = st.builds(
    Fn,
    name=name_st,
    params=st.lists(st.builds(Param, name=name_st, ty=st.one_of(st.none(), type_st)), max_size=3),
    ret=st.one_of(st.none(), type_st),
    fx=st.one_of(st.none(), fx_st),
    pre=st.just([]),
    post=st.just([]),
    body=st.lists(stmt_st, min_size=1, max_size=3).map(lambda ss: E.SigilBlock(stmts=ss)),
)

module_st = st.builds(
    Module,
    name=name_st,
    imports=st.lists(st.builds(Import, module=name_st, names=st.just([])), max_size=2),
    defs=st.lists(fn_st, min_size=1, max_size=2),
)


@settings(max_examples=150, deadline=None)
@given(module_st)
def test_parse_print_round_trips_generated_asts(mod: Module) -> None:
    assert parse_module(print_module(mod)) == mod
