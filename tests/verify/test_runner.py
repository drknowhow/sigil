"""Verify runner: subprocess isolation, timeout, verdict cache, binding rules.

Phase 3 exit gate (plan section 4): re-running verify on unchanged code is a
cache hit (<50 ms); a failing contract blocks binding and reports which
clause failed, with values.
"""

import time

from sigil.core.ast import Fn, Goal
from sigil.core.hash import digest_node
from sigil.lang.parser import parse_module
from sigil.store.repo import Store
from sigil.verify.runner import run_verify

GOOD = """module m

goal triple {
  intent: "triples a number"
  in: n Int
  out: Int
  fx: pure
  verify:
    out == n * 3
    out % 3 == 0
}

fn triple(n Int) -> Int
  pure
{
  ret n * 3
}
"""

BAD = GOOD.replace("ret n * 3", "ret n * 2")
LOOP = GOOD.replace("ret n * 3", "while true {\n    n := n + 1\n  }\n  ret n")
CRASH = GOOD.replace("ret n * 3", "ret undefined_helper(n)")


def _hashes(src: str) -> tuple[str, str]:
    mod = parse_module(src)
    goal = next(d for d in mod.defs if isinstance(d, Goal))
    fn = next(d for d in mod.defs if isinstance(d, Fn))
    return digest_node(goal), digest_node(fn)


def test_pass_binds_goal_to_impl(tmp_path) -> None:
    store = Store.create(tmp_path)
    v = run_verify(store, parse_module(GOOD), "triple", inputs={"n": 3})
    assert v.status == "pass" and not v.cached
    assert all(ok for _, ok, _ in v.clauses)
    gh, ih = _hashes(GOOD)
    assert store.status(gh) == "verified"
    assert store.binding(gh)["impl"] == ih


def test_fail_blocks_binding_and_reports_clause_with_values(tmp_path) -> None:
    store = Store.create(tmp_path)
    v = run_verify(store, parse_module(BAD), "triple", inputs={"n": 3})
    assert v.status == "fail"
    gh, _ = _hashes(BAD)
    assert store.status(gh) == "provisional"  # failing never binds
    failing = [(text, det) for text, ok, det in v.clauses if not ok]
    assert failing, v.clauses
    text, detail = failing[0]
    assert text == "out == n * 3"
    assert "6" in detail and "3" in detail  # out value and input value visible


def test_unchanged_code_is_a_cache_hit_under_50ms(tmp_path) -> None:
    store = Store.create(tmp_path)
    run_verify(store, parse_module(GOOD), "triple", inputs={"n": 3})
    t0 = time.perf_counter()
    v2 = run_verify(store, parse_module(GOOD), "triple", inputs={"n": 3})
    dt = time.perf_counter() - t0
    assert v2.cached and v2.status == "pass"
    assert dt < 0.05, f"cache hit took {dt * 1000:.1f}ms (gate: <50ms)"


def test_changed_impl_misses_cache(tmp_path) -> None:
    store = Store.create(tmp_path)
    run_verify(store, parse_module(GOOD), "triple", inputs={"n": 3})
    changed = GOOD.replace("ret n * 3", "ret 3 * n")  # different AST, same behavior
    v = run_verify(store, parse_module(changed), "triple", inputs={"n": 3})
    assert not v.cached and v.status == "pass"


def test_failures_are_cached_too(tmp_path) -> None:
    store = Store.create(tmp_path)
    run_verify(store, parse_module(BAD), "triple", inputs={"n": 3})
    v2 = run_verify(store, parse_module(BAD), "triple", inputs={"n": 3})
    assert v2.cached and v2.status == "fail"


def test_infinite_loop_caught_by_timeout_and_never_binds(tmp_path) -> None:
    store = Store.create(tmp_path)
    t0 = time.perf_counter()
    v = run_verify(store, parse_module(LOOP), "triple", inputs={"n": 3}, timeout=1.0)
    assert v.status == "timeout"
    assert time.perf_counter() - t0 < 10
    gh, _ = _hashes(LOOP)
    assert store.status(gh) == "provisional"


def test_timeouts_are_not_cached(tmp_path) -> None:
    store = Store.create(tmp_path)
    run_verify(store, parse_module(LOOP), "triple", inputs={"n": 3}, timeout=1.0)
    v2 = run_verify(store, parse_module(LOOP), "triple", inputs={"n": 3}, timeout=1.0)
    assert not v2.cached  # transient verdicts never enter the immutable cache


def test_crashing_impl_is_subprocess_isolated(tmp_path) -> None:
    store = Store.create(tmp_path)
    v = run_verify(store, parse_module(CRASH), "triple", inputs={"n": 3})
    # v1.2: per-case call exceptions are caught in the child -> structured
    # 'fail' with the exception as clause detail (still subprocess-isolated,
    # still never binds). This process is alive to assert it.
    assert v.status == "fail"
    assert any("undefined_helper" in (d or "") for _t, ok, d in v.clauses if not ok)
    gh, _ = _hashes(CRASH)
    assert store.status(gh) == "provisional"


def test_missing_inputs_is_actionable(tmp_path) -> None:
    import pytest

    store = Store.create(tmp_path)
    with pytest.raises(ValueError, match="(?s)inputs.*Remedy"):
        run_verify(store, parse_module(GOOD), "triple", inputs=None)
