"""v1.1 gate: @sigil.bind — Python-native entry point (lifter frontend)."""

import importlib.util
import sys
from pathlib import Path

import pytest

from sigil import SigilBindError, verify_bound
from sigil.store.repo import Store

GOOD = """
import sigil

@sigil.bind(verify=["out == n * 3"], fx="pure", store={store!r})
def triple(n):
    return n * 3
"""

BAD_IMPL = GOOD.replace("return n * 3", "return n * 2")

FX_VIOLATION = """
import sigil

@sigil.bind(verify=["out.len >= 0"], fx="pure", store={store!r})
def sneaky(p):
    return open(p, "w").write(p)
"""


def _import(tmp_path: Path, source: str, name: str):
    f = tmp_path / f"{name}.py"
    f.write_text(source.format(store=str(tmp_path)))
    spec = importlib.util.spec_from_file_location(name, f)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.modules.pop(name, None)
    return mod


def test_bind_registers_goal_and_impl_provisional(tmp_path) -> None:
    _import(tmp_path, GOOD, "m_good")
    store = Store.open(tmp_path)
    entries = {e["name"]: (gh, e) for gh, e in store.goals().items()}
    assert "triple" in entries
    gh, entry = entries["triple"]
    assert entry.get("lang") == "python"
    assert store.status(gh) == "provisional"  # registration never binds


def test_bind_verify_pass_binds_fail_stays_provisional(tmp_path) -> None:
    _import(tmp_path, GOOD, "m_good2")
    store = Store.open(tmp_path)
    v = verify_bound(tmp_path, "triple", inputs={"n": 4})
    assert v.status == "pass"
    gh = next(g for g, e in store.goals().items() if e["name"] == "triple")
    assert store.status(gh) == "verified"

    (tmp_path / "sub").mkdir()
    _import(tmp_path / "sub", BAD_IMPL, "m_bad")
    v2 = verify_bound(tmp_path / "sub", "triple", inputs={"n": 4})
    assert v2.status == "fail"
    store2 = Store.open(tmp_path / "sub")
    gh2 = next(g for g, e in store2.goals().items() if e["name"] == "triple")
    assert store2.status(gh2) == "provisional"


def test_bind_static_fx_violation_fails_at_import(tmp_path) -> None:
    with pytest.raises(SigilBindError, match="(?s)sneaky.*pure.*!fs.write.*Remedy"):
        _import(tmp_path, FX_VIOLATION, "m_fx")


def test_bind_records_inputs_reference(tmp_path) -> None:
    src = GOOD.replace(
        'fx="pure", store={store!r})', 'fx="pure", store={store!r}, inputs={{"n": 4}})'
    )
    _import(tmp_path, src, "m_inputs")
    store = Store.open(tmp_path)
    entry = next(e for e in store.goals().values() if e["name"] == "triple")
    assert entry.get("inputs") == {"n": 4}
