"""canon -> uncanon -> source -> canon is a fixed point (expand projection)."""

import ast
from pathlib import Path

from sigil.core.hash import digest_data
from sigil.core.pycanon import canon_node, canonical_fn, host_source

ROOT = Path(__file__).parent.parent.parent


def test_uncanon_round_trips_every_demo_function() -> None:
    tree = ast.parse((ROOT / "seed" / "demo_module.py").read_text())
    for fn in [n for n in tree.body if isinstance(n, ast.FunctionDef)]:
        data = canonical_fn(fn)
        src = host_source(data)  # projection
        re_data = canonical_fn(ast.parse(src).body[0])
        assert digest_data(re_data) == digest_data(data), fn.name


def test_uncanon_round_trips_oss_modules() -> None:
    for f in sorted((ROOT / "tests/fixtures/oss/requests").glob("*.py"))[:5]:
        tree = ast.parse(f.read_text())
        data = canon_node(tree)
        src = host_source(data)
        assert digest_data(canon_node(ast.parse(src))) == digest_data(data), f.name
