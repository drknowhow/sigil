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


def _disp(eff: tuple[str, str | None]) -> str:
    return f"!{eff[0]}.{eff[1]}" if eff[1] else f"!{eff[0]}"


def _admits(budget: set[tuple[str, str | None]], eff: tuple[str, str | None]) -> bool:
    """(name, None) in the budget admits every mode; a moded budget entry
    admits only that mode. Inferred unmoded effects need an unmoded grant."""
    return (eff[0], None) in budget or eff in budget


def _budget_set(row) -> set[tuple[str, str | None]]:
    return {(e.name, e.mode) for e in row.effects}


def _reachable(facts: dict, start: str) -> dict[tuple, tuple[list[str], str]]:
    """(name, mode) -> (call chain from start, reason), via BFS (first = shortest)."""
    out: dict[tuple, tuple[list[str], str]] = {}
    queue: list[tuple[str, list[str]]] = [(start, [start])]
    seen = {start}
    while queue:
        key, path = queue.pop(0)
        f = facts.get(key)
        if f is None:
            continue
        shown = [p for p in path if not p.startswith("__")]
        for name, mode, _unc in sorted(f.effects, key=lambda t: (t[0], t[1] or "")):
            out.setdefault((name, mode), (shown, f.reasons.get(name, "?")))
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

    if mod.fx is not None:  # module-wide budget (v1.1): every fn must satisfy it
        mbudget = _budget_set(mod.fx)
        for fn in fns.values():
            for eff, (chain, reason) in sorted(_reachable(facts, fn.name).items()):
                if not _admits(mbudget, eff):
                    errors.append(
                        f"module budget exceeded by fn {fn.name!r}:\n"
                        f"  {' -> '.join(chain)}: {reason} requires {_disp(eff)}; "
                        f"module budget allows {pfx(mod.fx)}\n"
                        f"Remedy: remove the call, or widen the module fx: budget."
                    )

    for fn in fns.values():
        if fn.fx is None:
            continue  # undeclared: row is inferred, nothing to hold it against
        declared = _budget_set(fn.fx)
        for eff, (chain, reason) in sorted(_reachable(facts, fn.name).items()):
            if not _admits(declared, eff):
                errors.append(
                    f"fn {fn.name!r} declares '{pfx(fn.fx)}' but its body requires {_disp(eff)}:\n"
                    f"  {' -> '.join(chain)}: {reason} requires {_disp(eff)}\n"
                    f"Remedy: remove the effectful call, or declare {_disp(eff)} on the fn."
                )

    for goal in (d for d in mod.defs if isinstance(d, Goal)):
        budget = _budget_set(goal.fx) if goal.fx is not None else set()
        if ("unsafe", None) in budget and goal.ack is None:
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
            if not _admits(budget, eff):
                budget_disp = pfx(goal.fx) if goal.fx is not None else "pure"
                errors.append(
                    f"effect budget exceeded for goal {goal.name!r}:\n"
                    f"  {' -> '.join(chain)}: {reason} requires {_disp(eff)}; "
                    f"budget allows {budget_disp}\n"
                    f"Remedy: remove the effectful call, or extend the goal's fx: "
                    f"budget with {_disp(eff)}(<scope>) if intended."
                )
    return errors
