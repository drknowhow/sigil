"""Harness core: lift idempotence, expand stability, patch auto-verify (R3)."""

import shutil
from pathlib import Path

from sigil.harness.core import Harness

ROOT = Path(__file__).parent.parent.parent

SIGIL_SRC = """module m

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
  ret n * 2
}
"""


def _harness_with_module(tmp_path) -> tuple:
    h = Harness(tmp_path)
    info = h.load_sigil_source(SIGIL_SRC)  # registers module + goal + fn in store
    return h, info


def test_lift_is_idempotent_and_supersede_on_change(tmp_path) -> None:
    h = Harness(tmp_path)
    src = tmp_path / "demo.py"
    shutil.copy(ROOT / "seed" / "demo_module.py", src)
    h.lift(str(src))
    n_lines = len(h.sheet().splitlines())
    r2 = h.lift(str(src))
    assert "unchanged" in r2.lower() or r2 == ""
    assert len(h.sheet().splitlines()) == n_lines  # nothing re-appended
    # change one function -> exactly one supersede line
    src.write_text(src.read_text().replace("min(60.0,", "min(30.0,"))
    h.lift(str(src))
    new_lines = h.sheet().splitlines()[n_lines:]
    assert len(new_lines) == 1 and " -> " in new_lines[0] and "jitter_backoff" in new_lines[0]


def test_expand_is_byte_identical_and_logged(tmp_path) -> None:
    h, info = _harness_with_module(tmp_path)
    fn_hash = info["fns"]["triple"]
    a = h.expand(fn_hash)
    b = h.expand("#" + fn_hash[:8])
    assert a == b and "ret n * 2" in a
    assert h.session_stats()["expansions"] == 2


def test_patch_auto_verifies_and_binds_on_pass(tmp_path) -> None:
    h, info = _harness_with_module(tmp_path)
    fn_hash = info["fns"]["triple"]
    result = h.patch(
        fn_hash,
        [{"path": "body.stmts.0.value.right.val", "op": "replace", "value": "3"}],
        inputs={"n": 5},
    )
    assert result["new_hash"] != fn_hash
    assert result["verify"]["status"] == "pass"
    assert h.store.status(info["goals"]["triple"]) == "verified"
    # R1: supersede line appended
    assert " -> " in h.sheet().splitlines()[-1]


def test_patch_failure_feedback_is_structured_and_small(tmp_path) -> None:
    h, info = _harness_with_module(tmp_path)
    result = h.patch(
        info["fns"]["triple"],
        [{"path": "body.stmts.0.value.right.val", "op": "replace", "value": "4"}],
        inputs={"n": 5},
    )
    v = result["verify"]
    assert v["status"] == "fail"
    failing = [c for c in v["clauses"] if not c[1]]
    assert failing and failing[0][0] == "out == n * 3"
    assert "20" in (failing[0][2] or "")  # observed value
    assert result["target_subtree"]  # where to aim the next patch
    assert len(str(result)) < 1200  # R3: failure responses stay small
    assert h.store.status(info["goals"]["triple"]) == "provisional"


def test_patch_without_goal_reports_unverified(tmp_path) -> None:
    h = Harness(tmp_path)
    src = tmp_path / "demo.py"
    shutil.copy(ROOT / "seed" / "demo_module.py", src)
    h.lift(str(src))
    fn_hash = next(iter(h.lifted_fns().values()))
    result = h.patch(fn_hash, [{"path": "name", "op": "replace", "value": "renamed"}])
    assert result["verify"] == "unverified: no goal bound"


def test_sheet_prefix_stable_across_all_ops(tmp_path) -> None:
    h, info = _harness_with_module(tmp_path)
    snapshots = [h.sheet()]
    h.expand(info["fns"]["triple"])
    snapshots.append(h.sheet())
    h.patch(
        info["fns"]["triple"],
        [{"path": "body.stmts.0.value.right.val", "op": "replace", "value": "3"}],
        inputs={"n": 2},
    )
    snapshots.append(h.sheet())
    for earlier, later in zip(snapshots, snapshots[1:], strict=False):
        assert later.startswith(earlier)
