"""Transpile Sigil AST -> runnable Python (sigil-transpile-verify skill).

Mapping: fn -> def with hints; pre/post -> assertions gated by
__sigil_contracts__ (stripped under SIGIL_RELEASE=1); post binds the result
via an inner __<name>_impl wrapper; goal -> generated test_<goal> module;
effect rows -> NO runtime artifact (static check in effectcheck.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sigil.core import expr as E
from sigil.core.ast import Fn, Goal, Invariant, Module, Node, Param, TypeExpr
from sigil.lang.printer import pexpr as sigil_text

TYPE_MAP = {
    "Str": "str",
    "Int": "int",
    "F64": "float",
    "U64": "int",
    "Bool": "bool",
    "Map": "dict",
    "None": "None",
}
PYBIN = {"and": "and", "or": "or", "in": "in"}

PRELUDE = '''import os as _os

__sigil_contracts__ = _os.environ.get("SIGIL_RELEASE") != "1"


def __sigil_set_insert(s, x):
    """Sigil Set.insert: add if absent, return whether it was added."""
    if x in s:
        return False
    s.add(x)
    return True
'''


@dataclass(frozen=True)
class TranspileResult:
    module_name: str
    python_src: str
    test_modules: dict[str, str] = field(default_factory=dict)


def ptype_hint(t: TypeExpr | None) -> str | None:
    if t is None:
        return None
    if t.name == "[]":
        inner = ptype_hint(t.args[0])
        return f"list[{inner}]" if inner else "list"
    if t.name in TYPE_MAP:
        return TYPE_MAP[t.name]
    return None  # unknown host type: omit the hint (D-017)


def texpr(e: Node) -> str:
    if isinstance(e, E.ELit):
        if e.lit == "str":
            return repr(e.val)
        if e.lit == "bool":
            return "True" if e.val == "true" else "False"
        if e.lit == "none":
            return "None"
        return e.val
    if isinstance(e, E.EName):
        return e.id
    if isinstance(e, E.EAttr):
        if e.attr == "len":
            return f"len({texpr(e.value)})"
        if e.attr == "set":
            return f"set({texpr(e.value)})"
        if e.attr == "keys":
            return f"list(({texpr(e.value)}).keys())"
        return f"({texpr(e.value)}).{e.attr}"
    if isinstance(e, E.ECall):
        if isinstance(e.func, E.EAttr) and e.func.attr == "insert":
            args = ", ".join(texpr(a) for a in e.args)
            return f"__sigil_set_insert({texpr(e.func.value)}, {args})"
        args = ", ".join(texpr(a) for a in e.args)
        return f"{texpr(e.func)}({args})"
    if isinstance(e, E.EIndex):
        return f"{texpr(e.value)}[{texpr(e.index)}]"
    if isinstance(e, E.EBin):
        op = PYBIN.get(e.op, e.op)
        return f"({texpr(e.left)} {op} {texpr(e.right)})"
    if isinstance(e, E.EUn):
        return f"(not {texpr(e.value)})" if e.op == "not" else f"(-{texpr(e.value)})"
    if isinstance(e, E.EList):
        return "[" + ", ".join(texpr(x) for x in e.items) + "]"
    if isinstance(e, E.ESet):
        return "{" + ", ".join(texpr(x) for x in e.items) + "}" if e.items else "set()"
    if isinstance(e, E.EMap):
        return "{" + ", ".join(f"{texpr(p.key)}: {texpr(p.value)}" for p in e.items) + "}"
    if isinstance(e, E.EComp):
        s = f"[{texpr(e.elt)} for {e.var} in {texpr(e.iter)}"
        for g in e.guards:
            s += f" if {texpr(g)}"
        return s + "]"
    raise TypeError(f"cannot transpile expression node {type(e).__name__}")


def tstmt(s: Node, ind: int) -> list[str]:
    pad = "    " * ind
    if isinstance(s, E.SAssign):
        return [f"{pad}{texpr(s.target)} = {texpr(s.value)}"]
    if isinstance(s, E.SRet):
        return [f"{pad}return {texpr(s.value)}" if s.value is not None else f"{pad}return"]
    if isinstance(s, E.SExpr):
        return [f"{pad}{texpr(s.value)}"]
    if isinstance(s, E.SIf):
        lines = [f"{pad}if {texpr(s.cond)}:"]
        lines += [ln for sub in s.then for ln in tstmt(sub, ind + 1)] or [f"{pad}    pass"]
        if s.orelse:
            lines.append(f"{pad}else:")
            lines += [ln for sub in s.orelse for ln in tstmt(sub, ind + 1)]
        return lines
    if isinstance(s, E.SFor):
        lines = [f"{pad}for {s.var} in {texpr(s.iter)}:"]
        return lines + ([ln for sub in s.body for ln in tstmt(sub, ind + 1)] or [f"{pad}    pass"])
    if isinstance(s, E.SWhile):
        lines = [f"{pad}while {texpr(s.cond)}:"]
        return lines + ([ln for sub in s.body for ln in tstmt(sub, ind + 1)] or [f"{pad}    pass"])
    raise TypeError(f"cannot transpile statement node {type(s).__name__}")


def _sig(params: list[Param]) -> str:
    parts = []
    for p in params:
        hint = ptype_hint(p.ty)
        parts.append(f"{p.name}: {hint}" if hint else p.name)
    return ", ".join(parts)


def tfn(fn: Fn) -> list[str]:
    body = fn.body.stmts if isinstance(fn.body, E.SigilBlock) else []
    ret_hint = ptype_hint(fn.ret)
    arrow = f" -> {ret_hint}" if ret_hint else ""
    argnames = ", ".join(p.name for p in fn.params)
    if not fn.pre and not fn.post:
        lines = [f"def {fn.name}({_sig(fn.params)}){arrow}:"]
        lines += [ln for s in body for ln in tstmt(s, 1)] or ["    pass"]
        return lines
    # Contract wrapper: pre checks, impl call, post checks with result binder.
    lines = [f"def {fn.name}({_sig(fn.params)}){arrow}:"]
    for c in fn.pre:
        lines.append("    if __sigil_contracts__:")
        lines.append(f"        assert {texpr(c.expr)}, {('pre failed: ' + sigil_text(c.expr))!r}")
    lines.append(f"    __r = __{fn.name}_impl({argnames})")
    for c in fn.post:
        lines.append("    if __sigil_contracts__:")
        lines.append(f"        {c.binder} = __r")
        lines.append(f"        assert {texpr(c.expr)}, {('post failed: ' + sigil_text(c.expr))!r}")
    lines.append("    return __r")
    lines.append("")
    lines.append("")
    lines.append(f"def __{fn.name}_impl({_sig(fn.params)}){arrow}:")
    lines += [ln for s in body for ln in tstmt(s, 1)] or ["    pass"]
    return lines


def tgoal_test(goal: Goal, module_name: str) -> str:
    clauses = [(sigil_text(v.expr), texpr(v.expr)) for v in goal.verify]
    innames = ", ".join(p.name for p in goal.inputs)
    sig = ("out, " + innames) if innames else "out"
    lines = [
        f'"""Generated from goal {goal.name!r} (module {module_name}).',
        "",
        f"Inputs come from a pytest fixture named {goal.name}_inputs (docs/decisions.md D-013).",
        '"""',
        "",
        f"def run_verify({sig}):",
        '    """Evaluate every verify clause; returns [(clause_text, passed)]."""',
        "    results = []",
    ]
    for text, py in clauses:
        lines.append(f"    results.append(({text!r}, bool({py})))")
    lines += [
        "    return results",
        "",
        "",
        f"def test_{goal.name}({goal.name}_inputs):",
        f"    from {module_name} import {goal.name}",
        f"    out = {goal.name}(**{goal.name}_inputs)",
        f"    checks = run_verify(out, **{goal.name}_inputs)",
        "    failures = [c for c, ok in checks if not ok]",
        '    assert not failures, "verify failed: " + repr(failures)',
    ]
    return "\n".join(lines) + "\n"


def transpile_module(mod: Module) -> TranspileResult:
    parts = [f'"""Generated by sigil build from module {mod.name!r} — edit the .sg, not this."""']
    for imp in mod.imports:
        parts.append(f"import {imp.module}")
    parts.append(PRELUDE)
    tests: dict[str, str] = {}
    for d in mod.defs:
        if isinstance(d, Fn):
            parts.append("\n".join(tfn(d)) + "\n")
        elif isinstance(d, Goal):
            tests[f"test_{d.name}"] = tgoal_test(d, mod.name)
        elif isinstance(d, Invariant):
            pass  # invariants execute via the verify runner, not generated tests
    return TranspileResult(
        module_name=mod.name, python_src="\n\n".join(parts) + "\n", test_modules=tests
    )
