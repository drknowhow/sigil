"""Transpiler: Sigil -> Python. Contracts gate on env; bodies run correctly."""

import os
import textwrap

import pytest

from sigil.lang.parser import parse_module
from sigil.transpile.python import transpile_module

DEDUPE = """module dd

fn dedupe(xs [Int]) -> [Int]
  pure
  post |r| r.set == xs.set ∧ r.len ≤ xs.len
{
  s := {}
  ret [x | x <- xs, s.insert(x)]
}
"""


def _exec(py_src: str, env_release: bool = False):
    ns = {}
    old = os.environ.get("SIGIL_RELEASE")
    os.environ["SIGIL_RELEASE"] = "1" if env_release else "0"
    try:
        exec(compile(py_src, "<gen>", "exec"), ns)
    finally:
        if old is None:
            os.environ.pop("SIGIL_RELEASE", None)
        else:
            os.environ["SIGIL_RELEASE"] = old
    return ns


def test_dedupe_transpiles_and_runs() -> None:
    result = transpile_module(parse_module(DEDUPE))
    ns = _exec(result.python_src)
    assert ns["dedupe"]([3, 1, 3, 2, 1]) == [3, 1, 2]


def test_violated_postcondition_raises_in_dev() -> None:
    bad = DEDUPE.replace("ret [x | x <- xs, s.insert(x)]", "ret [x | x <- xs, true]")
    bad = bad.replace("r.len ≤ xs.len", "r.len < xs.len")  # dup input must now fail
    result = transpile_module(parse_module(bad))
    ns = _exec(result.python_src)
    with pytest.raises(AssertionError, match="post"):
        ns["dedupe"]([1, 1])


def test_release_mode_strips_contracts() -> None:
    bad = DEDUPE.replace("r.len ≤ xs.len", "r.len < xs.len")
    result = transpile_module(parse_module(bad))
    ns = _exec(result.python_src, env_release=True)
    ns["dedupe"]([1, 1])  # post violated but not checked in release


def test_precondition_checked() -> None:
    src = textwrap.dedent("""\
    module m

    fn half(n Int) -> Int
      pure
      pre n % 2 == 0
    {
      ret n // 2
    }
    """)
    ns = _exec(transpile_module(parse_module(src)).python_src)
    assert ns["half"](8) == 4
    with pytest.raises(AssertionError, match="pre"):
        ns["half"](7)


def test_control_flow_and_collections() -> None:
    src = textwrap.dedent("""\
    module m

    fn tally(xs [Int]) -> Map
    {
      d := {:}
      for x <- xs {
        if x in d {
          d[x] := d[x] + 1
        } else {
          d[x] := 1
        }
      }
      ret d
    }
    """)
    ns = _exec(transpile_module(parse_module(src)).python_src)
    assert ns["tally"]([1, 2, 1]) == {1: 2, 2: 1}


def test_goal_generates_test_module() -> None:
    src = textwrap.dedent("""\
    module m

    goal triple {
      intent: "triples"
      in: n Int
      out: Int
      fx: pure
      verify:
        out == n * 3
    }

    fn triple(n Int) -> Int
      pure
    {
      ret n * 3
    }
    """)
    result = transpile_module(parse_module(src))
    assert "test_triple" in result.test_modules
    test_src = result.test_modules["test_triple"]
    ns = _exec(result.python_src)
    tns = {"triple": ns["triple"]}
    exec(compile(test_src.split("def test_")[0], "<gentest>", "exec"), tns)
    assert tns["run_verify"](out=9, n=3) == [("out == n * 3", True)]
    assert tns["run_verify"](out=8, n=3) == [("out == n * 3", False)]
