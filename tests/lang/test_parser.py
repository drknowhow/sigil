"""Parser units: structure, errors with cause+remedy, lvalue validation."""

import pytest

from sigil.core import expr as E
from sigil.lang.parser import parse_module

GOAL = """module m

goal g {
  intent: "x"
  in: xs [Str]
  out: Map
  fx: !net(h.com) !unsafe
  ack: "vetted subprocess use"
  verify:
    xs.len ≥ 0
    g(xs).len == xs.len
}
"""


def test_goal_fields() -> None:
    mod = parse_module(GOAL)
    g = mod.defs[0]
    assert g.name == "g"
    assert g.intent == "x"
    assert [p.name for p in g.inputs] == ["xs"]
    assert g.output.name == "Map"
    assert [e.name for e in g.fx.effects] == ["net", "unsafe"]
    assert g.fx.effects[0].scope == "h.com"
    assert len(g.verify) == 2


def test_contracts_carry_binder() -> None:
    src = "module m\n\nfn f(x Int) -> Int\n  pre x > 0\n  post |r| r ≥ x\n{\n  ret x\n}\n"
    fn = parse_module(src).defs[0]
    assert fn.pre[0].mode == "pre" and fn.pre[0].binder is None
    assert fn.post[0].mode == "post" and fn.post[0].binder == "r"


def test_missing_brace_is_actionable() -> None:
    with pytest.raises(ValueError, match="(?s)line.*[Rr]emedy"):
        parse_module("module m\n\nfn f() {\n  ret 1\n")


def test_bad_assignment_target_is_actionable() -> None:
    with pytest.raises(ValueError, match="(?s)assign.*[Rr]emedy"):
        parse_module("module m\n\nfn f() {\n  1 := 2\n}\n")


def test_comments_never_reach_ast() -> None:
    a = parse_module("module m\n\nfn f() {\n  ret 1\n}\n")
    b = parse_module("module m\n-- top comment\n\nfn f() { -- inline\n  ret 1 -- trailing\n}\n")
    assert a == b


def test_comprehension_shape() -> None:
    src = "module m\n\nfn f(xs [Int]) -> [Int]\n{\n  ret [x * 2 | x <- xs, x > 0]\n}\n"
    ret = parse_module(src).defs[0].body.stmts[0]
    comp = ret.value
    assert isinstance(comp, E.EComp)
    assert comp.var == "x" and len(comp.guards) == 1
