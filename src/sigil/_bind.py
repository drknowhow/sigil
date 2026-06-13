"""@sigil.bind — the Python-native entry point (v1.1, roadmap item 2).

The decorator is a *lifter frontend*: the user writes ordinary Python; on
import Sigil lifts the function through the same canonicalizer, hashes it,
registers/refreshes its goal in the store, and snapshots the defining
module's source for the verify runner. Importing never runs verification
(no subprocess at import time) and never binds — verification happens via
verify_bound() / `sigil verify` / `sigil check` / the harness (R3 intact).

A declared fx= budget IS checked statically at import: catching a sneaked-in
`open(..., "w")` at the earliest possible moment is the point.
"""

from __future__ import annotations

import ast as pyast
import inspect
import textwrap
from pathlib import Path


class SigilBindError(ValueError):
    """Raised at import when a bound function violates its declared budget."""


def bind(
    goal: str | None = None,
    verify: list[str] | None = None,
    inputs: dict | None = None,
    fx: str | None = None,
    store: str | Path = ".",
):
    def deco(fn):
        from sigil.core.ast import Goal, HostBlock, Param, VerifyClause
        from sigil.lang.parser import Parser, parse_fxrow, tokenize
        from sigil.lift.python import lift_source
        from sigil.store.repo import Store
        from sigil.transpile.effectcheck import _admits, _budget_set, _disp

        src = textwrap.dedent(inspect.getsource(fn))
        tree = pyast.parse(src)
        fndef = tree.body[0]
        fndef.decorator_list = []  # bind metadata is not identity
        cleaned = pyast.unparse(pyast.fix_missing_locations(tree))
        fnode = lift_source(cleaned, name=fn.__module__ or "bound").module.defs[0]

        declared = parse_fxrow(fx) if fx is not None else None
        if declared is not None:
            budget = _budget_set(declared)
            inferred = {(e.name, e.mode) for e in (fnode.fx.effects if fnode.fx else [])}
            bad = sorted(e for e in inferred if not _admits(budget, e))
            if bad:
                raise SigilBindError(
                    f"@sigil.bind: {fn.__name__!r} declares fx={fx!r} but its body "
                    f"requires {', '.join(_disp(e) for e in bad)}. Remedy: remove "
                    "the effectful call or widen the declared fx budget."
                )

        st = Store.create(Path(store))
        impl_hash = st.put(fnode)
        # snapshot the defining module's source for the verify runner
        module_src = Path(fn.__code__.co_filename).read_text(encoding="utf-8")
        snapshot = HostBlock(lang="py-module-src", data=module_src)
        snapshot_hash = st.put(snapshot)

        goal_name = goal or fn.__name__
        if verify is not None:
            clauses = []
            for text in verify:
                p = Parser(tokenize(text))
                clauses.append(VerifyClause(expr=p.expr()))
            sig = inspect.signature(fn)
            params = [Param(name=n) for n in sig.parameters]
            goal_node = Goal(
                name=goal_name,
                intent=f"bound from {fn.__module__}",
                inputs=params,
                fx=declared,
                verify=clauses,
            )
            goal_hash = st.put(goal_node)
        else:
            goal_hash = st.resolve(goal_name) if goal else None
            if goal_hash is None:
                raise SigilBindError(
                    f"@sigil.bind on {fn.__name__!r} needs verify=[...] clauses or "
                    "goal=<hash-or-name of an existing store goal>. Remedy: add one."
                )
        extra = {"lang": "python", "impl": impl_hash, "fn": fn.__name__}
        if inputs is not None:
            extra["inputs"] = inputs
        st.register_goal(goal_hash, module_hash=snapshot_hash, name=goal_name, extra=extra)
        fn.__sigil__ = {"goal": goal_hash, "impl": impl_hash, "store": str(store)}
        return fn

    return deco


def verify_bound(
    store_dir: str | Path, goal_name: str, inputs: dict | None = None, timeout: float = 10.0
):
    """Run a bound (python) goal's verify clauses; pass binds goal<->impl."""
    from sigil.store.repo import Store
    from sigil.verify.runner import run_verify_py

    st = Store.open(Path(store_dir))
    matches = [(gh, e) for gh, e in st.goals().items() if e["name"] == goal_name]
    if not matches:
        raise ValueError(
            f"No goal named {goal_name!r} in the store. Remedy: import the module "
            "that declares @sigil.bind first (binding registers on import)."
        )
    goal_hash, entry = matches[0]
    goal_node = st.get(goal_hash)
    snapshot = st.get(entry["module"])
    return run_verify_py(
        st, snapshot.data, entry.get("fn", goal_name), goal_node, inputs, timeout=timeout
    )
