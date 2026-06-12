"""Full pipeline (plan section 7): lift -> patch -> verify -> transpile -> execute."""

from pathlib import Path

from sigil.harness.core import Harness
from sigil.transpile.build import build_source

ROOT = Path(__file__).parent.parent.parent

SIGIL = """module pipe

goal double_all {
  intent: "double every element"
  in: xs [Int]
  out: [Int]
  fx: pure
  verify:
    out.len == xs.len
    out.set == [x * 2 | x <- xs].set
}

fn double_all(xs [Int]) -> [Int]
  pure
{
  ret [x * 3 | x <- xs]
}
"""


def test_lift_patch_verify_transpile_execute(tmp_path) -> None:
    h = Harness(tmp_path)

    # lift real python alongside (Tier 1+2)
    src = tmp_path / "legacy.py"
    src.write_text((ROOT / "seed" / "demo_module.py").read_text())
    assert "lifted" in h.lift(str(src))

    # load the Sigil module with a seeded bug; verify fails
    info = h.load_sigil_source(SIGIL, name="pipe")
    v0 = h.verify(info["goals"]["double_all"], inputs={"xs": [1, 2]})
    assert v0["status"] == "fail"

    # patch the multiplier 3 -> 2; auto-verify passes and binds
    r = h.patch(
        info["fns"]["double_all"],
        [{"path": "body.stmts.0.value.elt.right.val", "op": "replace", "value": "2"}],
        inputs={"xs": [1, 2]},
    )
    assert r["verify"]["status"] == "pass"

    # transpile the PATCHED module from the store and execute it
    entry = h.store.goals()[info["goals"]["double_all"]]
    module = h.store.get(entry["module"])
    py = build_source(
        __import__("sigil.lang.printer", fromlist=["print_module"]).print_module(module)
    ).python_src
    ns: dict = {}
    exec(compile(py, "<pipe>", "exec"), ns)
    assert ns["double_all"]([4, 5]) == [8, 10]
