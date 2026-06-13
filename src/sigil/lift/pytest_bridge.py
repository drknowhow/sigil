"""pytest bridge (v2.0, P2.6 narrow): parametrize tables -> REVIEWABLE goal
drafts. Tier-3 trust applies: output is a proposal for a human/agent to
review and verify - never auto-registered as a spec."""

from __future__ import annotations

import ast


def _literal(node: ast.expr):
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError):
        return None


def extract_drafts(test_source: str, name: str = "<tests>") -> list[dict]:
    tree = ast.parse(test_source)
    drafts: list[dict] = []
    for fn in [n for n in tree.body if isinstance(n, ast.FunctionDef)]:
        if not fn.name.startswith("test_"):
            continue
        # @pytest.mark.parametrize("a,b,expected" | ("a","b","expected"), [...])
        rows, names = None, None
        for dec in fn.decorator_list:
            if (
                isinstance(dec, ast.Call)
                and isinstance(dec.func, ast.Attribute)
                and dec.func.attr == "parametrize"
                and len(dec.args) >= 2
            ):
                raw = _literal(dec.args[0])
                if isinstance(raw, str):
                    names = [p.strip() for p in raw.split(",")]
                elif isinstance(raw, (tuple, list)):
                    names = list(raw)
                table = _literal(dec.args[1])
                if names and isinstance(table, list):
                    rows = [r if isinstance(r, (tuple, list)) else (r,) for r in table]
        if not rows or not names:
            continue
        # body: assert f(args...) == <expected-name>; derive the expected
        # column from the comparison RHS, not a hard-coded "expected" name
        # (V2_REPORT minor: a "n,exp" table extracted 0 drafts before).
        target = None
        expected_col = None
        for stmt in ast.walk(fn):
            if (
                isinstance(stmt, ast.Assert)
                and isinstance(stmt.test, ast.Compare)
                and isinstance(stmt.test.left, ast.Call)
                and isinstance(stmt.test.left.func, ast.Name)
                and len(stmt.test.ops) == 1
                and isinstance(stmt.test.ops[0], ast.Eq)
            ):
                call = stmt.test.left
                rhs = stmt.test.comparators[0]
                if (
                    all(isinstance(a, ast.Name) for a in call.args)
                    and isinstance(rhs, ast.Name)
                    and rhs.id in names
                ):
                    target = (call.func.id, [a.id for a in call.args])
                    expected_col = rhs.id
        if target is None or expected_col is None:
            continue
        fname, params = target
        cases = [dict(zip(names, row, strict=False)) for row in rows]
        first = cases[0]
        exp_val = first[expected_col]
        sg = (
            f"module {fname}_proposed\n\n"
            f"goal {fname} {{\n"
            f'  intent: "REVIEW ME: proposed from {name}::{fn.name} (pytest bridge)"\n'
            f"  in: {', '.join(params)}\n"
            f'  inputs: "{fname}.inputs.json"\n'
            f"  verify:\n"
            f"    out == {exp_val}\n"
            f"}}\n"
        )
        drafts.append(
            {
                "fn": fname,
                "params": params,
                "sg": sg,
                "inputs": {k: v for k, v in first.items() if k in params},
                "cases": cases,
                "source_test": fn.name,
            }
        )
    return drafts
