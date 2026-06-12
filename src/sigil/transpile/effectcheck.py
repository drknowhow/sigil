"""Static effect-budget check (sigil-transpile-verify skill).

Reuses lift/effects.py's analyzer — one implementation, two callers. A goal's
fx: line is a budget; the implementation's inferred row must be a subset or
the build fails, naming the violating call chain. Comparison is by effect
NAME; scopes are carried but not enforced in v1.0 (docs/decisions.md D-015).
Uncertain effects (!unsafe?) count as present — never silence uncertainty.
"""

from __future__ import annotations

import ast

from sigil.core.ast import Fn, Goal, Module
from sigil.lang.printer import pfx
from sigil.lift.effects import analyze_module


def _reachable(facts: dict, start: str) -> dict[str, tuple[list[str], str]]:
    """effect name -> (call chain from start, reason), via BFS (first = shortest)."""
    out: dict[str, tuple[list[str], str]] = {}
    queue: list[tuple[str, list[str]]] = [(start, [start])]
    seen = {start}
    while queue:
        key, path = queue.pop(0)
        f = facts.get(key)
        if f is None:
            continue
        shown = [p for p in path if not p.startswith("__")]
        for eff, _unc in sorted(f.effects):
            out.setdefault(eff, (shown, f.reasons.get(eff, "?")))
        for c in sorted(f.callees):
            if c not in seen:
                seen.add(c)
                queue.append((c, path + [c]))
    return out


def check_module(mod: Module, python_src: str) -> list[str]:
    """Returns a list of violation messages (empty = build may proceed)."""
    facts = analyze_module(ast.parse(python_src))
    errors: list[str] = []
    fns = {d.name: d for d in mod.defs if isinstance(d, Fn)}

    for fn in fns.values():
        if fn.fx is None:
            continue  # undeclared: row is inferred, nothing to hold it against
        declared = {e.name for e in fn.fx.effects}
        for eff, (chain, reason) in sorted(_reachable(facts, fn.name).items()):
            if eff not in declared:
                errors.append(
                    f"fn {fn.name!r} declares '{pfx(fn.fx)}' but its body requires !{eff}:\n"
                    f"  {' -> '.join(chain)}: {reason} requires !{eff}\n"
                    f"Remedy: remove the effectful call, or declare !{eff} on the fn."
                )

    for goal in (d for d in mod.defs if isinstance(d, Goal)):
        budget = {e.name for e in goal.fx.effects} if goal.fx is not None else set()
        if "unsafe" in budget and goal.ack is None:
            errors.append(
                f"goal {goal.name!r} budgets !unsafe without an ack: line.\n"
                'Remedy: add ack: "<reason>" to the goal, acknowledging the escape hatch.'
            )
        impl = fns.get(goal.name)
        if impl is None:
            errors.append(
                f"goal {goal.name!r} has no implementation fn of the same name.\n"
                f"Remedy: define fn {goal.name}(...) in this module "
                "(store-based bindings arrive in Phase 3)."
            )
            continue
        for eff, (chain, reason) in sorted(_reachable(facts, goal.name).items()):
            if eff not in budget:
                budget_disp = pfx(goal.fx) if goal.fx is not None else "pure"
                errors.append(
                    f"effect budget exceeded for goal {goal.name!r}:\n"
                    f"  {' -> '.join(chain)}: {reason} requires !{eff}; "
                    f"budget allows {budget_disp}\n"
                    f"Remedy: remove the effectful call, or extend the goal's fx: "
                    f"budget with !{eff}(<scope>) if intended."
                )
    return errors
