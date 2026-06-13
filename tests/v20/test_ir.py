"""v2.0 gate: language-neutral IR (S1) — Python lowers to it, hashes are
stable under formatting, the renderer round-trips, legacy objects stay
readable."""

import ast
from pathlib import Path

from sigil.core.hash import digest_data
from sigil.core.ir import IR_VERSION, ir_source, is_ir, lower_fn, lower_module

ROOT = Path(__file__).parent.parent.parent


def _fn_ir(src: str):
    return lower_fn(ast.parse(src).body[0])


def test_ir_is_tagged_and_versioned() -> None:
    ir = _fn_ir("def f(a, b):\n    return a + b\n")
    assert is_ir(ir)
    assert ir[0] == "def" and IR_VERSION == 2


def test_formatting_and_docstrings_never_move_ir_hashes() -> None:
    a = _fn_ir("def f(a, b):\n    return a + b\n")
    b = _fn_ir('def f(a, b):\n    """doc"""\n    # comment\n    return a + b\n')
    assert digest_data(a) == digest_data(b)
    c = _fn_ir("def f(a, b):\n    return a - b\n")
    assert digest_data(a) != digest_data(c)


def test_ir_round_trips_through_source() -> None:
    # lower -> render -> parse -> lower is a fixed point (expand projection)
    for f in [
        ROOT / "seed" / "demo_module.py",
        *sorted((ROOT / "tests/fixtures/oss/requests").glob("*.py"))[:6],
    ]:
        tree = ast.parse(f.read_text())
        ir = lower_module(tree)
        src2 = ir_source(ir)
        ir2 = lower_module(ast.parse(src2))
        assert digest_data(ir2) == digest_data(ir), f.name


def test_exotic_constructs_host_wrap_not_crash() -> None:
    src = (
        "async def agen():\n"
        "    async with open('x') as f:\n"
        "        async for line in f:\n"
        "            yield line\n"
        "\n"
        "def matcher(x):\n"
        "    match x:\n"
        "        case [1, *rest]:\n"
        "            return rest\n"
        "        case _:\n"
        "            return None\n"
    )
    ir = lower_module(ast.parse(src))
    assert is_ir(ir)  # wrapped or lowered — never an exception
    ir_source(ir)  # and renderable


def test_lifted_fns_now_carry_ir_and_legacy_still_expands(tmp_path) -> None:
    from sigil.core.ast import Fn, HostBlock
    from sigil.harness.core import Harness

    h = Harness(tmp_path)
    f = tmp_path / "m.py"
    f.write_text("def half(n):\n    return n / 2\n")
    h.lift(str(f))
    node = h.store.get(h.lifted_fns()["half"])
    assert is_ir(node.body.data)
    assert "return n / 2" in h.expand(h.lifted_fns()["half"])

    # legacy (v1 pycanon-shaped) object: still readable through expand
    from sigil.core.pycanon import canon_node

    legacy = Fn(
        name="old",
        body=HostBlock(
            lang="python", data=canon_node(ast.parse("def old():\n    return 1\n").body[0])
        ),
    )
    lh = h.store.put(legacy)
    assert "return 1" in h.expand(lh)
