"""v1.1 gate: effect modes (read/write), !db, and module-level budgets."""

import ast as pyast
import textwrap
from pathlib import Path

import pytest

from sigil.core.ast import Effect, EffectRow
from sigil.lang.parser import parse_module
from sigil.lang.printer import pfx, print_module
from sigil.lift.effects import infer_module_effects
from sigil.lift.python import check_module_budget, lift_source
from sigil.transpile.build import BuildError, build_source


def test_mode_grammar_round_trips() -> None:
    src = (
        "module m\n"
        "fx: !db !fs.read(./config) !net(api.x.com)\n\n"
        "fn f(p Str) -> Str\n  !fs.read\n{\n  ret p\n}\n"
    )
    mod = parse_module(src)
    assert mod.fx is not None
    eff = mod.fx.effects[1]
    assert eff.name == "fs" and eff.mode == "read" and eff.scope == "./config"
    assert print_module(mod) == src


def test_mode_inference_read_only() -> None:
    src = Path("tests/fixtures/effects/case_034.py").read_text()
    rows = infer_module_effects(pyast.parse(src))
    effs = {(e.name, e.mode) for e in rows["load_config"].effects}
    assert ("fs", "read") in effs
    assert ("fs", "write") not in effs and ("fs", None) not in effs


def test_mode_inference_write_and_db() -> None:
    src = "def dump(p, data):\n    open(p, 'w').write(data)\n"
    rows = infer_module_effects(pyast.parse(src))
    assert {(e.name, e.mode) for e in rows["dump"].effects} == {("fs", "write")}
    src2 = Path("tests/fixtures/effects/case_035.py").read_text()
    rows2 = infer_module_effects(pyast.parse(src2))
    assert any(e.name == "db" for e in rows2["save_row"].effects)


def test_read_and_write_collapse_to_unmoded() -> None:
    src = "def rw(p):\n    d = open(p).read()\n    open(p, 'w').write(d)\n    return d\n"
    rows = infer_module_effects(pyast.parse(src))
    assert [(e.name, e.mode) for e in rows["rw"].effects] == [("fs", None)]


def test_goal_budget_mode_semantics() -> None:
    base = textwrap.dedent("""\
    module m

    goal slurp {
      intent: "read a file"
      in: p Str
      out: Str
      fx: !fs.read
      verify:
        out.len ≥ 0
    }

    fn slurp(p Str) -> Str
      !fs.read
    {
      ret open(p).read()
    }
    """)
    assert build_source(base).python_src  # read within read budget: ok
    writer = base.replace("ret open(p).read()", 'ret open(p, "w").write(p)')
    writer = writer.replace(
        "fn slurp(p Str) -> Str\n  !fs.read", "fn slurp(p Str) -> Str\n  !fs.write"
    )
    with pytest.raises(BuildError, match="(?s)!fs.write.*budget allows !fs.read.*Remedy"):
        build_source(writer)


def test_unmoded_budget_admits_both_modes() -> None:
    src = textwrap.dedent("""\
    module m

    goal rw {
      intent: "read and write"
      in: p Str
      out: Str
      fx: !fs
      verify:
        out.len ≥ 0
    }

    fn rw(p Str) -> Str
      !fs
    {
      d := open(p).read()
      open(p, "w").write(d)
      ret d
    }
    """)
    assert build_source(src).python_src


def test_sg_module_budget_enforced() -> None:
    src = textwrap.dedent("""\
    module m
    fx: !fs.read

    fn sneaky(p Str) -> Str
    {
      ret open(p, "w").write(p)
    }
    """)
    with pytest.raises(BuildError, match="(?s)module budget.*sneaky.*!fs.write.*Remedy"):
        build_source(src)


def test_py_module_budget_via_dunder() -> None:
    src = (
        '__sigil_fx__ = "!fs.read !net"\n\nimport requests\n\n'
        "def ok(u):\n    return requests.get(u)\n\n"
        'def bad(p):\n    open(p, "w").write("x")\n'
    )
    violations = check_module_budget(src)
    assert violations and "bad" in violations[0] and "!fs.write" in violations[0]
    clean = src.replace('def bad(p):\n    open(p, "w").write("x")\n', "")
    assert check_module_budget(clean) == []


def test_lift_result_carries_module_fx() -> None:
    src = '__sigil_fx__ = "!fs.read"\n\ndef f(p):\n    return open(p).read()\n'
    result = lift_source(src, name="m")
    assert result.module_fx is not None
    assert pfx(result.module_fx) == "!fs.read"


def test_effect_mode_survives_serialization() -> None:
    from sigil.core.ast import from_data, to_data

    row = EffectRow(effects=[Effect(name="fs", scope="./x", uncertain=False, mode="read")])
    assert from_data(to_data(row)) == row
