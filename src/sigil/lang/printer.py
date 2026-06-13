"""Printer: AST -> canonical Sigil text. The printer DEFINES canonical form —
one true formatting, no options (sigil-transpile-verify skill). Glyphs are
emitted; ASCII aliases are parse-only (docs/grammar.md alias table)."""

from __future__ import annotations

from sigil.core import expr as E
from sigil.core.ast import Contract, EffectRow, Fn, Goal, Module, Node, Param, TypeExpr

GLYPH = {"and": "∧", "or": "∨", "<=": "≤", ">=": "≥", "!=": "≠"}
PREC = {
    "or": 1,
    "and": 2,
    "==": 4,
    "!=": 4,
    "<": 4,
    "<=": 4,
    ">": 4,
    ">=": 4,
    "in": 4,
    "+": 5,
    "-": 5,
    "*": 6,
    "/": 6,
    "//": 6,
    "%": 6,
    "**": 7,
}
_ESC = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\t": "\\t"}


def _prec(e: Node) -> int:
    if isinstance(e, E.EBin):
        return PREC[e.op]
    if isinstance(e, E.EUn):
        return 3 if e.op == "not" else 8
    if isinstance(e, (E.EAttr, E.ECall, E.EIndex)):
        return 9
    return 10


def pexpr(e: Node, minprec: int = 0) -> str:
    s = _expr(e)
    return f"({s})" if _prec(e) < minprec else s


def _expr(e: Node) -> str:
    if isinstance(e, E.ELit):
        if e.lit == "str":
            return '"' + "".join(_ESC.get(c, c) for c in e.val) + '"'
        return e.val
    if isinstance(e, E.EName):
        return e.id
    if isinstance(e, E.EAttr):
        return f"{pexpr(e.value, 9)}.{e.attr}"
    if isinstance(e, E.ECall):
        return f"{pexpr(e.func, 9)}({', '.join(pexpr(a) for a in e.args)})"
    if isinstance(e, E.EIndex):
        return f"{pexpr(e.value, 9)}[{pexpr(e.index)}]"
    if isinstance(e, E.EUn):
        if e.op == "not":
            return f"¬{pexpr(e.value, 3)}"
        return f"-{pexpr(e.value, 9)}"
    if isinstance(e, E.EBin):
        p = PREC[e.op]
        if e.op in ("==", "!=", "<", "<=", ">", ">=", "in"):
            lmin, rmin = 5, 5  # comparisons do not chain (grammar)
        elif e.op == "**":
            lmin, rmin = 8, 7  # right-associative
        else:
            lmin, rmin = p, p + 1
        op = GLYPH.get(e.op, e.op)
        return f"{pexpr(e.left, lmin)} {op} {pexpr(e.right, rmin)}"
    if isinstance(e, E.EList):
        return "[" + ", ".join(pexpr(x) for x in e.items) + "]"
    if isinstance(e, E.ESet):
        return "{" + ", ".join(pexpr(x) for x in e.items) + "}"
    if isinstance(e, E.EMap):
        if not e.items:
            return "{:}"
        return "{" + ", ".join(f"{pexpr(p.key)}: {pexpr(p.value)}" for p in e.items) + "}"
    if isinstance(e, E.EComp):
        s = f"[{pexpr(e.elt)} | {e.var} <- {pexpr(e.iter)}"
        for g in e.guards:
            s += f", {pexpr(g)}"
        return s + "]"
    if isinstance(e, str):  # opaque expression text (lifted Tier-3 contracts)
        return e
    raise TypeError(f"cannot print expression node {type(e).__name__}")


def ptype(t: TypeExpr) -> str:
    if t.name == "[]":
        return f"[{ptype(t.args[0])}]"
    if t.args:
        return t.name + "[" + ", ".join(ptype(a) for a in t.args) + "]"
    return t.name


def pparams(params: list[Param]) -> str:
    return ", ".join(p.name + (f" {ptype(p.ty)}" if p.ty else "") for p in params)


def pfx(row: EffectRow) -> str:
    if not row.effects:
        return "pure"
    out = []
    for e in row.effects:
        s = f"!{e.name}"
        if e.mode:
            s += f".{e.mode}"
        if e.scope:
            s += f"({e.scope})"
        if e.uncertain:
            s += "?"
        out.append(s)
    return " ".join(out)


def _stmt(s: Node, ind: int) -> list[str]:
    pad = "  " * ind
    if isinstance(s, E.SAssign):
        return [f"{pad}{pexpr(s.target)} := {pexpr(s.value)}"]
    if isinstance(s, E.SRet):
        return [f"{pad}ret {pexpr(s.value)}" if s.value is not None else f"{pad}ret"]
    if isinstance(s, E.SExpr):
        return [f"{pad}{pexpr(s.value)}"]
    if isinstance(s, E.SIf):
        lines = [f"{pad}if {pexpr(s.cond)} {{"]
        for sub in s.then:
            lines += _stmt(sub, ind + 1)
        if s.orelse:
            lines += [f"{pad}}} else {{"]
            for sub in s.orelse:
                lines += _stmt(sub, ind + 1)
        lines += [f"{pad}}}"]
        return lines
    if isinstance(s, E.SFor):
        lines = [f"{pad}for {s.var} <- {pexpr(s.iter)} {{"]
        for sub in s.body:
            lines += _stmt(sub, ind + 1)
        return lines + [f"{pad}}}"]
    if isinstance(s, E.SWhile):
        lines = [f"{pad}while {pexpr(s.cond)} {{"]
        for sub in s.body:
            lines += _stmt(sub, ind + 1)
        return lines + [f"{pad}}}"]
    raise TypeError(f"cannot print statement node {type(s).__name__}")


def _contract(c: Contract) -> str:
    if c.mode == "pre":
        return f"  pre {pexpr(c.expr)}"
    return f"  post |{c.binder}| {pexpr(c.expr)}"


def pfn(fn: Fn) -> str:
    head = f"fn {fn.name}({pparams(fn.params)})"
    if fn.ret is not None:
        head += f" -> {ptype(fn.ret)}"
    lines = [head]
    if fn.fx is not None:
        lines.append(f"  {pfx(fn.fx)}")
    lines += [_contract(c) for c in fn.pre]
    lines += [_contract(c) for c in fn.post]
    lines.append("{")
    body = fn.body.stmts if isinstance(fn.body, E.SigilBlock) else []
    for s in body:
        lines += _stmt(s, 1)
    lines.append("}")
    return "\n".join(lines)


def pgoal(g: Goal) -> str:
    lines = [f"goal {g.name} {{"]
    if g.intent:
        esc = "".join(_ESC.get(c, c) for c in g.intent)
        lines.append(f'  intent: "{esc}"')
    if g.inputs:
        lines.append(f"  in: {pparams(g.inputs)}")
    if g.output is not None:
        lines.append(f"  out: {ptype(g.output)}")
    if g.fx is not None:
        lines.append(f"  fx: {pfx(g.fx)}")
    for law in g.laws:
        esc = "".join(_ESC.get(c, c) for c in law.text)
        lines.append(f'  law: "{esc}"')
    if g.ack is not None:
        esc = "".join(_ESC.get(c, c) for c in g.ack)
        lines.append(f'  ack: "{esc}"')
    if g.inputs_ref is not None:
        esc = "".join(_ESC.get(c, c) for c in g.inputs_ref)
        lines.append(f'  inputs: "{esc}"')
    if g.verify:
        lines.append("  verify:")
        for v in g.verify:
            lines.append(f"    {pexpr(v.expr)}")
    lines.append("}")
    return "\n".join(lines)


def print_module(mod: Module) -> str:
    head = f"module {mod.name}"
    if mod.fx is not None:
        head += f"\nfx: {pfx(mod.fx)}"
    parts = [head]
    for imp in mod.imports:
        parts.append(f"use {imp.module}")
    for d in mod.defs:
        if isinstance(d, Goal):
            parts.append(pgoal(d))
        elif isinstance(d, Fn):
            parts.append(pfn(d))
        else:
            raise TypeError(f"cannot print top-level node {type(d).__name__}")
    return "\n\n".join(parts) + "\n"
