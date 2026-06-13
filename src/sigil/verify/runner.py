"""Verify runner (plan Phase 3, sigil-transpile-verify skill).

Hard rule: untrusted code never runs in-process. The transpiled module and
every verify clause execute in a SUBPROCESS with a timeout (10s default).
Verdicts are cached by (goal_hash, impl_hash) — content-addressed, never
expire. Pass/fail are cached; timeout/error are transient and are not
(decisions.md D-019). A passing run binds goal<->impl in the store; anything
else leaves the goal provisional.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import dataclass, field

from sigil.core.ast import Fn, Goal, Module
from sigil.core.hash import digest_data, digest_node
from sigil.lang.printer import pexpr as sigil_text
from sigil.transpile.python import texpr, transpile_module

SENTINEL = "__SIGIL_VERDICT__"
DEFAULT_TIMEOUT = 10.0


@dataclass(frozen=True)
class Verdict:
    status: str  # pass | fail | timeout | error
    goal_hash: str
    impl_hash: str
    clauses: list = field(default_factory=list)  # [(text, ok, detail)]
    cached: bool = False
    duration_ms: float = 0.0
    detail: str | None = None  # stderr tail / exception (failures only)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "goal_hash": self.goal_hash,
            "impl_hash": self.impl_hash,
            "clauses": self.clauses,
            "duration_ms": round(self.duration_ms, 2),
            "detail": self.detail,
        }


def _harness(goal: Goal, fn_name: str | None, cases: list[dict]) -> str:
    """Per-clause evaluation code appended to the module: every clause is
    evaluated for every input case, in ONE subprocess (v1.2)."""
    lines = [
        "",
        "import json as __json",
        f"__cases = __json.loads({json.dumps(json.dumps(cases))})",
        "__results = []",
        "for __i, __inputs in enumerate(__cases):",
        *(
            [
                "    try:",
                f"        __out = {fn_name}(**__inputs)",
                "    except Exception as __e:",
                "        __results.append([__i, '<call>', False, repr(__e)[:300]])",
                "        continue",
            ]
            if fn_name
            else ["    __out = None"]
        ),
    ]
    for v in goal.verify:
        text, py = sigil_text(v.expr), texpr(v.expr)
        bindings = "; ".join([f"{p.name} = __inputs[{p.name!r}]" for p in goal.inputs])
        lines += [
            "    try:",
            f"        out = __out; {bindings}" if bindings else "        out = __out",
            f"        __ok = bool({py})",
            "        __detail = None if __ok else "
            "'out=' + repr(__out)[:300] + ' inputs=' + repr(__inputs)[:300]",
            f"        __results.append([__i, {text!r}, __ok, __detail])",
            "    except Exception as __e:",
            f"        __results.append([__i, {text!r}, False, repr(__e)[:300]])",
        ]
    lines += [
        "print()",
        f"print({SENTINEL!r} + __json.dumps(__results))",
    ]
    return "\n".join(lines)


def run_verify(
    store, module: Module, goal_name: str, inputs: dict | None, timeout: float = DEFAULT_TIMEOUT
) -> Verdict:
    goal = next((d for d in module.defs if isinstance(d, Goal) and d.name == goal_name), None)
    if goal is None:
        raise ValueError(
            f"Goal {goal_name!r} not found in module {module.name!r}. "
            "Remedy: check the goal name ('sigil lift' or the sheet lists goals)."
        )
    fn = next((d for d in module.defs if isinstance(d, Fn) and d.name == goal_name), None)
    if fn is None:
        raise ValueError(
            f"Goal {goal_name!r} has no same-name implementation fn (decisions.md D-016). "
            f"Remedy: define fn {goal_name}(...) in the module."
        )
    goal_hash, impl_hash = digest_node(goal), digest_node(fn)
    if inputs is None:
        inputs = store.recorded_inputs(goal_hash)  # v1.2: D-020 revisited
    if inputs is None:
        if goal.inputs:
            names = ", ".join(p.name for p in goal.inputs)
            raise ValueError(
                f"Goal {goal_name!r} needs inputs ({names}) to run its verify clauses. "
                'Remedy: pass --inputs <file.json>, add inputs: "file" to the goal, '
                "or record them via @sigil.bind(inputs=...)."
            )
        inputs = {}

    inputs_hash = digest_data(inputs)[:16]
    cached = store.cache_get(goal_hash, impl_hash, inputs_hash)
    if cached is not None:
        return Verdict(cached=True, **{**cached, "goal_hash": goal_hash, "impl_hash": impl_hash})

    py_src = transpile_module(module).python_src
    return _execute(store, goal, goal_name, py_src, inputs, timeout, goal_hash, impl_hash)


def run_verify_py(
    store,
    module_source: str,
    fn_name: str,
    goal,
    inputs: dict | None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Verdict:
    """Verify a @sigil.bind'ed PYTHON implementation: same runner, the
    snapshot module source executes instead of transpiled Sigil (v1.1)."""
    if inputs is None and goal.inputs:
        names = ", ".join(p.name for p in goal.inputs)
        raise ValueError(
            f"Goal {goal.name!r} needs inputs ({names}). Remedy: pass inputs= "
            "or record them via @sigil.bind(inputs=...)."
        )
    goal_hash = digest_node(goal)
    if inputs is None:
        inputs = store.recorded_inputs(goal_hash)
    impl_hash = digest_data(module_source)
    inputs_hash = digest_data(inputs or {})[:16]
    cached = store.cache_get(goal_hash, impl_hash, inputs_hash)
    if cached is not None:
        return Verdict(cached=True, **{**cached, "goal_hash": goal_hash, "impl_hash": impl_hash})
    # Neutralize sigil inside the child: verification must never re-register
    # bindings, and the subprocess may not have sigil importable at all.
    shim = (
        "import sys as __sys, types as __types\n"
        "__shim = __types.ModuleType('sigil')\n"
        "__shim.bind = lambda *a, **k: (lambda f: f)\n"
        "__shim.SigilBindError = Exception\n"
        "__shim.verify_bound = None\n"
        "__sys.modules['sigil'] = __shim\n"
    )
    return _execute(
        store, goal, fn_name, shim + module_source, inputs or {}, timeout, goal_hash, impl_hash
    )


def _execute(
    store,
    goal,
    fn_name: str,
    py_src: str,
    inputs: dict,
    timeout: float,
    goal_hash: str,
    impl_hash: str,
) -> Verdict:
    inputs_hash = digest_data(inputs or {})[:16]
    script = py_src + _harness(goal, fn_name, [inputs])
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            # stdin must NOT be inherited: under the stdio MCP transport the
            # server's stdin IS the client's JSON-RPC pipe — an inherited
            # handle deadlocks served verify and would let untrusted code
            # read client traffic (firstuse report, 2026-06-12; D-029).
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        ms = (time.perf_counter() - t0) * 1000
        return Verdict(
            status="timeout",
            goal_hash=goal_hash,
            impl_hash=impl_hash,
            duration_ms=ms,
            detail=f"verify exceeded {timeout}s and was killed; never binds",
        )
    ms = (time.perf_counter() - t0) * 1000

    line = next((ln for ln in proc.stdout.splitlines() if ln.startswith(SENTINEL)), None)
    if proc.returncode != 0 or line is None:
        tail = (proc.stderr or proc.stdout).strip().splitlines()[-3:]
        return Verdict(
            status="error",
            goal_hash=goal_hash,
            impl_hash=impl_hash,
            duration_ms=ms,
            detail="; ".join(tail) or "no verdict produced",
        )

    rows = json.loads(line[len(SENTINEL) :])
    clauses = [(text, ok, detail) for _i, text, ok, detail in rows]
    status = "pass" if all(ok for _, ok, _ in clauses) else "fail"
    verdict = Verdict(
        status=status, goal_hash=goal_hash, impl_hash=impl_hash, clauses=clauses, duration_ms=ms
    )
    store.cache_put(
        goal_hash,
        impl_hash,
        {"status": status, "clauses": clauses, "duration_ms": round(ms, 2), "detail": None},
        inputs_hash,
    )
    if status == "pass":
        store.bind(goal_hash, impl_hash)  # binding only on pass
    return verdict


def run_verify_many(
    store, module, goal_name: str, cases: list[dict], timeout: float = DEFAULT_TIMEOUT
) -> dict:
    """Evaluate every verify clause over many input cases in ONE subprocess.
    Property-generation backend (v1.2): never cached, never binds."""
    from sigil.core.ast import Goal as _Goal

    goal = next((d for d in module.defs if isinstance(d, _Goal) and d.name == goal_name), None)
    if goal is None:
        raise ValueError(f"Goal {goal_name!r} not found. Remedy: check the name.")
    py_src = transpile_module(module).python_src
    script = py_src + _harness(goal, goal_name, cases)
    try:
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "failures": [], "cases": len(cases)}
    line = next((ln for ln in proc.stdout.splitlines() if ln.startswith(SENTINEL)), None)
    if proc.returncode != 0 or line is None:
        tail = (proc.stderr or proc.stdout).strip().splitlines()[-3:]
        return {"status": "error", "failures": [], "cases": len(cases), "detail": "; ".join(tail)}
    rows = json.loads(line[len(SENTINEL) :])
    failures = [(i, text, detail) for i, text, ok, detail in rows if not ok]
    return {"status": "fail" if failures else "pass", "failures": failures, "cases": len(cases)}


def run_verify_invariant(
    store, module, inv_name: str, inputs: dict | None, timeout: float = DEFAULT_TIMEOUT
) -> dict:
    """Verify a multi-fn invariant (v2.0): clauses call the implicated
    functions directly; passing binds the invariant to ALL their impl hashes."""
    from sigil.core.ast import Fn as _Fn
    from sigil.core.ast import Goal as _Goal
    from sigil.core.ast import Invariant as _Inv

    inv = next((d for d in module.defs if isinstance(d, _Inv) and d.name == inv_name), None)
    if inv is None:
        raise ValueError(f"Invariant {inv_name!r} not found. Remedy: check the name.")
    fns = {d.name: d for d in module.defs if isinstance(d, _Fn)}
    missing = [n for n in inv.over if n not in fns]
    if missing:
        raise ValueError(
            f"Invariant {inv_name!r} ranges over undefined fns: {', '.join(missing)}. "
            "Remedy: define them in the module."
        )
    inv_hash = digest_node(inv)
    if inputs is None:
        inputs = store.recorded_inputs(inv_hash)
    if inputs is None and inv.inputs:
        raise ValueError(
            f'Invariant {inv_name!r} needs inputs. Remedy: pass inputs= or add inputs: "file.json".'
        )
    shim = _Goal(name=inv.name, inputs=inv.inputs, verify=inv.verify)
    py_src = transpile_module(module).python_src
    script = py_src + _harness(shim, None, [inputs or {}])
    try:
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return {"name": inv_name, "status": "timeout", "clauses": []}
    line = next((ln for ln in proc.stdout.splitlines() if ln.startswith(SENTINEL)), None)
    if proc.returncode != 0 or line is None:
        tail = (proc.stderr or proc.stdout).strip().splitlines()[-3:]
        return {"name": inv_name, "status": "error", "clauses": [], "detail": "; ".join(tail)}
    rows = json.loads(line[len(SENTINEL) :])
    clauses = [(text, ok, detail) for _i, text, ok, detail in rows]
    status = "pass" if all(ok for _, ok, _ in clauses) else "fail"
    if status == "pass":
        impls = {n: digest_node(fns[n]) for n in inv.over}
        index = store._read_index()
        index.setdefault("invariant_bindings", {})[inv_hash] = {"impls": impls}
        store._write_index(index)
    return {"name": inv_name, "status": status, "clauses": clauses, "invariant_hash": inv_hash}
