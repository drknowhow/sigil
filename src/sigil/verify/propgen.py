"""Property generation from typed contracts (v1.2, P2.7 modified).

Only fully-typed goals get generators — no guessing. Deterministic stdlib
RNG (seeded), so reports are reproducible. Counterexamples are appended to
the store as permanent regression inputs.
"""

from __future__ import annotations

import random

from sigil.core.ast import Goal, TypeExpr


def _gen_for(ty: TypeExpr | None, rng: random.Random):
    if ty is None:
        raise ValueError("untyped parameter")
    if ty.name == "[]":
        inner = ty.args[0]
        return [_gen_for(inner, rng) for _ in range(rng.randint(0, 5))]
    if ty.name == "Int" or ty.name == "U64":
        return rng.randint(-100, 100)
    if ty.name == "F64":
        return round(rng.uniform(-1000.0, 1000.0), 4)
    if ty.name == "Bool":
        return rng.random() < 0.5
    if ty.name == "Str":
        return "".join(rng.choice("abcdefgh xyz") for _ in range(rng.randint(0, 8)))
    raise ValueError(f"no generator for type {ty.name!r}")


def generate_inputs(goal: Goal, n: int, seed: int = 0) -> list[dict]:
    """N deterministic input cases for a fully-typed goal."""
    rng = random.Random(seed)
    untyped = [p.name for p in goal.inputs if p.ty is None]
    if untyped:
        raise ValueError(
            f"Goal {goal.name!r} has untyped inputs ({', '.join(untyped)}); "
            "property generation needs full types. Remedy: annotate the goal's "
            "in: parameters."
        )
    try:
        return [{p.name: _gen_for(p.ty, rng) for p in goal.inputs} for _ in range(n)]
    except ValueError as exc:
        raise ValueError(
            f"Goal {goal.name!r}: {exc}. Remedy: use Int/F64/Bool/Str/[T] types, "
            "or supply recorded inputs instead."
        ) from exc


def run_property_check(
    store, goal_ref: str, n: int = 50, seed: int = 0, timeout: float = 30.0
) -> dict:
    """Generate, run in one subprocess, record counterexamples permanently."""
    from sigil.verify.runner import run_verify_many

    goal_hash = store.resolve(goal_ref)
    goal = store.get(goal_hash)
    entry = store.goals().get(goal_hash)
    if entry is None or entry.get("module") is None:
        raise ValueError(f"Goal {goal_ref} has no registered module. Remedy: build/load it first.")
    module = store.get(entry["module"])
    cases = generate_inputs(goal, n=n, seed=seed)
    result = run_verify_many(store, module, goal.name, cases, timeout=timeout)
    counterexamples = []
    if result["status"] == "fail":
        seen = set()
        for idx, _text, _detail in result["failures"]:
            if idx not in seen:
                seen.add(idx)
                counterexamples.append(cases[idx])
        for cx in counterexamples[:5]:  # keep the ledger small but permanent
            store.append_counterexample(goal_hash, cx)
    return {
        "status": result["status"],
        "cases": result["cases"],
        "counterexamples": counterexamples,
        "detail": result.get("detail"),
    }
