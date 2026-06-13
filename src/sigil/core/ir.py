"""Language-neutral IR (v2.0, S1) — the canonical form lifted code hashes to.

Tagged lists: ["def", name, args, body, decorators, returns], ["call", f,
args, kwargs], ["nm", id], ["const", type, repr], ... Frontends lower their
ASTs into this; the store, sheet, patches, and hashes operate on it. Python
constructs outside the common subset host-wrap (["host", "python", <pycanon
form>]) — wrapped is honest, crashed is not. The renderer raises IR back to a
Python AST and unparses, so host wraps compose inside lowered parents.

One-way door, softened (D-036): new lifts are IR; v1 (pycanon-shaped) store
objects remain readable forever via the legacy path in `ir_source`.
"""

from __future__ import annotations

import ast

from sigil.core.pycanon import _strip_docstring, canon_node, uncanon

IR_VERSION = 2

_IR_TAGS = frozenset(
    {
        "module",
        "def",
        "class",
        "pyargs",
        "call",
        "kw",
        "nm",
        "const",
        "attr",
        "idx",
        "bin",
        "un",
        "boolop",
        "cmp",
        "assign",
        "aug",
        "ann",
        "ret",
        "if",
        "for",
        "while",
        "list",
        "tuple",
        "set",
        "dict",
        "comp",
        "gen",
        "lam",
        "fstr",
        "fmtv",
        "slice",
        "star",
        "tern",
        "named",
        "try",
        "h",
        "with",
        "item",
        "raise",
        "pass",
        "break",
        "continue",
        "import",
        "importfrom",
        "global",
        "nonlocal",
        "expr",
        "del",
        "yield",
        "yieldfrom",
        "await",
        "assert",
        "host",
    }
)

_BIN = {
    ast.Add: "+",
    ast.Sub: "-",
    ast.Mult: "*",
    ast.Div: "/",
    ast.FloorDiv: "//",
    ast.Mod: "%",
    ast.Pow: "**",
    ast.LShift: "<<",
    ast.RShift: ">>",
    ast.BitOr: "|",
    ast.BitXor: "^",
    ast.BitAnd: "&",
    ast.MatMult: "@",
}
_UN = {ast.Not: "not", ast.USub: "-", ast.UAdd: "+", ast.Invert: "~"}
_CMP = {
    ast.Eq: "==",
    ast.NotEq: "!=",
    ast.Lt: "<",
    ast.LtE: "<=",
    ast.Gt: ">",
    ast.GtE: ">=",
    ast.Is: "is",
    ast.IsNot: "is not",
    ast.In: "in",
    ast.NotIn: "not in",
}
_RBIN = {v: k for k, v in _BIN.items()}
_RUN = {v: k for k, v in _UN.items()}
_RCMP = {v: k for k, v in _CMP.items()}


def is_ir(data) -> bool:
    return isinstance(data, list) and bool(data) and data[0] in _IR_TAGS


def _host(node: ast.AST) -> list:
    return ["host", "python", canon_node(node)]


# ---------------- lowering: Python AST -> IR ----------------


def lower_expr(e: ast.expr) -> list:
    if isinstance(e, ast.Constant):
        v = e.value
        return ["const", type(v).__name__, repr(v)]
    if isinstance(e, ast.Name):
        return ["nm", e.id]
    if isinstance(e, ast.Attribute):
        return ["attr", lower_expr(e.value), e.attr]
    if isinstance(e, ast.Subscript):
        return ["idx", lower_expr(e.value), lower_expr(e.slice)]
    if isinstance(e, ast.Call):
        return [
            "call",
            lower_expr(e.func),
            [lower_expr(a) for a in e.args],
            [["kw", k.arg, lower_expr(k.value)] for k in e.keywords],
        ]
    if isinstance(e, ast.BinOp) and type(e.op) in _BIN:
        return ["bin", _BIN[type(e.op)], lower_expr(e.left), lower_expr(e.right)]
    if isinstance(e, ast.UnaryOp) and type(e.op) in _UN:
        return ["un", _UN[type(e.op)], lower_expr(e.operand)]
    if isinstance(e, ast.BoolOp):
        op = "and" if isinstance(e.op, ast.And) else "or"
        return ["boolop", op, [lower_expr(v) for v in e.values]]
    if isinstance(e, ast.Compare):
        return [
            "cmp",
            lower_expr(e.left),
            [[_CMP[type(o)], lower_expr(c)] for o, c in zip(e.ops, e.comparators, strict=True)],
        ]
    if isinstance(e, ast.IfExp):
        return ["tern", lower_expr(e.test), lower_expr(e.body), lower_expr(e.orelse)]
    if isinstance(e, ast.NamedExpr):
        return ["named", lower_expr(e.target), lower_expr(e.value)]
    if isinstance(e, ast.List):
        return ["list", [lower_expr(x) for x in e.elts]]
    if isinstance(e, ast.Tuple):
        return ["tuple", [lower_expr(x) for x in e.elts]]
    if isinstance(e, ast.Set):
        return ["set", [lower_expr(x) for x in e.elts]]
    if isinstance(e, ast.Dict):
        return [
            "dict",
            [lower_expr(k) if k is not None else ["star", 0] for k in e.keys],
            [lower_expr(v) for v in e.values],
        ]
    if isinstance(e, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
        kind = {"ListComp": "l", "SetComp": "s", "GeneratorExp": "g", "DictComp": "d"}[
            type(e).__name__
        ]
        if any(g.is_async for g in e.generators):
            return _host(e)
        elts = (
            [lower_expr(e.key), lower_expr(e.value)]
            if isinstance(e, ast.DictComp)
            else [lower_expr(e.elt)]
        )
        gens = [
            ["gen", lower_expr(g.target), lower_expr(g.iter), [lower_expr(i) for i in g.ifs]]
            for g in e.generators
        ]
        return ["comp", kind, elts, gens]
    if isinstance(e, ast.Lambda):
        return ["lam", ["pyargs", canon_node(e.args)], lower_expr(e.body)]
    if isinstance(e, ast.JoinedStr):
        return ["fstr", [lower_expr(v) for v in e.values]]
    if isinstance(e, ast.FormattedValue):
        spec = lower_expr(e.format_spec) if e.format_spec is not None else 0
        return ["fmtv", lower_expr(e.value), e.conversion, spec]
    if isinstance(e, ast.Slice):
        return [
            "slice",
            *(lower_expr(x) if x is not None else 0 for x in (e.lower, e.upper, e.step)),
        ]
    if isinstance(e, ast.Starred):
        return ["star", lower_expr(e.value)]
    if isinstance(e, ast.Await):
        return ["await", lower_expr(e.value)]
    if isinstance(e, ast.Yield):
        return ["yield", lower_expr(e.value) if e.value is not None else 0]
    if isinstance(e, ast.YieldFrom):
        return ["yieldfrom", lower_expr(e.value)]
    return _host(e)


def lower_stmt(s: ast.stmt) -> list:
    if isinstance(s, ast.FunctionDef):
        return [
            "def",
            s.name,
            ["pyargs", canon_node(s.args)],
            [lower_stmt(x) for x in _strip_docstring(list(s.body))],
            [lower_expr(d) for d in s.decorator_list],
            lower_expr(s.returns) if s.returns is not None else 0,
        ]
    if isinstance(s, ast.ClassDef):
        return [
            "class",
            s.name,
            [lower_expr(b) for b in s.bases],
            [lower_stmt(x) for x in _strip_docstring(list(s.body))],
            [lower_expr(d) for d in s.decorator_list],
            [["kw", k.arg, lower_expr(k.value)] for k in s.keywords],
        ]
    if isinstance(s, ast.Return):
        return ["ret", lower_expr(s.value) if s.value is not None else 0]
    if isinstance(s, ast.Assign):
        return ["assign", [lower_expr(t) for t in s.targets], lower_expr(s.value)]
    if isinstance(s, ast.AugAssign) and type(s.op) in _BIN:
        return ["aug", _BIN[type(s.op)], lower_expr(s.target), lower_expr(s.value)]
    if isinstance(s, ast.AnnAssign):
        return [
            "ann",
            lower_expr(s.target),
            lower_expr(s.annotation),
            lower_expr(s.value) if s.value is not None else 0,
            int(s.simple),
        ]
    if isinstance(s, ast.If):
        return [
            "if",
            lower_expr(s.test),
            [lower_stmt(x) for x in s.body],
            [lower_stmt(x) for x in s.orelse],
        ]
    if isinstance(s, ast.For):
        return [
            "for",
            lower_expr(s.target),
            lower_expr(s.iter),
            [lower_stmt(x) for x in s.body],
            [lower_stmt(x) for x in s.orelse],
        ]
    if isinstance(s, ast.While):
        return [
            "while",
            lower_expr(s.test),
            [lower_stmt(x) for x in s.body],
            [lower_stmt(x) for x in s.orelse],
        ]
    if isinstance(s, ast.Try):
        return [
            "try",
            [lower_stmt(x) for x in s.body],
            [
                [
                    "h",
                    lower_expr(h.type) if h.type is not None else 0,
                    h.name or 0,
                    [lower_stmt(x) for x in h.body],
                ]
                for h in s.handlers
            ],
            [lower_stmt(x) for x in s.orelse],
            [lower_stmt(x) for x in s.finalbody],
        ]
    if isinstance(s, ast.With):
        return [
            "with",
            [
                [
                    "item",
                    lower_expr(i.context_expr),
                    lower_expr(i.optional_vars) if i.optional_vars is not None else 0,
                ]
                for i in s.items
            ],
            [lower_stmt(x) for x in s.body],
        ]
    if isinstance(s, ast.Raise):
        return [
            "raise",
            lower_expr(s.exc) if s.exc is not None else 0,
            lower_expr(s.cause) if s.cause is not None else 0,
        ]
    if isinstance(s, ast.Pass):
        return ["pass"]
    if isinstance(s, ast.Break):
        return ["break"]
    if isinstance(s, ast.Continue):
        return ["continue"]
    if isinstance(s, ast.Import):
        return ["import", [[a.name, a.asname or 0] for a in s.names]]
    if isinstance(s, ast.ImportFrom):
        return ["importfrom", s.module or "", s.level, [[a.name, a.asname or 0] for a in s.names]]
    if isinstance(s, ast.Global):
        return ["global", list(s.names)]
    if isinstance(s, ast.Nonlocal):
        return ["nonlocal", list(s.names)]
    if isinstance(s, ast.Expr):
        return ["expr", lower_expr(s.value)]
    if isinstance(s, ast.Delete):
        return ["del", [lower_expr(t) for t in s.targets]]
    if isinstance(s, ast.Assert):
        return ["assert", lower_expr(s.test), lower_expr(s.msg) if s.msg is not None else 0]
    return _host(s)


def lower_fn(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> list:
    return lower_stmt(fn)


def lower_module(tree: ast.Module) -> list:
    return ["module", [lower_stmt(s) for s in _strip_docstring(list(tree.body))]]


# ---------------- raising: IR -> Python AST -> source ----------------


def _rx(d):  # raise expr
    if d == 0:
        return None
    tag = d[0]
    if tag == "const":
        text = d[2]
        return ast.Constant(value=... if text == "Ellipsis" else ast.literal_eval(text))
    if tag == "nm":
        return ast.Name(id=d[1], ctx=ast.Load())
    if tag == "attr":
        return ast.Attribute(value=_rx(d[1]), attr=d[2], ctx=ast.Load())
    if tag == "idx":
        return ast.Subscript(value=_rx(d[1]), slice=_rx(d[2]), ctx=ast.Load())
    if tag == "call":
        return ast.Call(
            func=_rx(d[1]),
            args=[_rx(a) for a in d[2]],
            keywords=[ast.keyword(arg=k[1], value=_rx(k[2])) for k in d[3]],
        )
    if tag == "bin":
        return ast.BinOp(left=_rx(d[2]), op=_RBIN[d[1]](), right=_rx(d[3]))
    if tag == "un":
        return ast.UnaryOp(op=_RUN[d[1]](), operand=_rx(d[2]))
    if tag == "boolop":
        return ast.BoolOp(
            op=ast.And() if d[1] == "and" else ast.Or(), values=[_rx(v) for v in d[2]]
        )
    if tag == "cmp":
        return ast.Compare(
            left=_rx(d[1]), ops=[_RCMP[o]() for o, _ in d[2]], comparators=[_rx(c) for _, c in d[2]]
        )
    if tag == "tern":
        return ast.IfExp(test=_rx(d[1]), body=_rx(d[2]), orelse=_rx(d[3]))
    if tag == "named":
        t = _rx(d[1])
        t.ctx = ast.Store()
        return ast.NamedExpr(target=t, value=_rx(d[2]))
    if tag == "list":
        return ast.List(elts=[_rx(x) for x in d[1]], ctx=ast.Load())
    if tag == "tuple":
        return ast.Tuple(elts=[_rx(x) for x in d[1]], ctx=ast.Load())
    if tag == "set":
        return ast.Set(elts=[_rx(x) for x in d[1]])
    if tag == "dict":
        return ast.Dict(
            keys=[None if k == ["star", 0] else _rx(k) for k in d[1]], values=[_rx(v) for v in d[2]]
        )
    if tag == "comp":
        gens = [
            ast.comprehension(
                target=_st(_rx(g[1])), iter=_rx(g[2]), ifs=[_rx(i) for i in g[3]], is_async=0
            )
            for g in d[3]
        ]
        if d[1] == "d":
            return ast.DictComp(key=_rx(d[2][0]), value=_rx(d[2][1]), generators=gens)
        cls = {"l": ast.ListComp, "s": ast.SetComp, "g": ast.GeneratorExp}[d[1]]
        return cls(elt=_rx(d[2][0]), generators=gens)
    if tag == "lam":
        return ast.Lambda(args=uncanon(d[1][1]), body=_rx(d[2]))
    if tag == "fstr":
        return ast.JoinedStr(values=[_rx(v) for v in d[1]])
    if tag == "fmtv":
        return ast.FormattedValue(
            value=_rx(d[1]), conversion=d[2], format_spec=_rx(d[3]) if d[3] != 0 else None
        )
    if tag == "slice":
        return ast.Slice(lower=_rx(d[1]), upper=_rx(d[2]), step=_rx(d[3]))
    if tag == "star":
        return ast.Starred(value=_rx(d[1]), ctx=ast.Load())
    if tag == "await":
        return ast.Await(value=_rx(d[1]))
    if tag == "yield":
        return ast.Yield(value=_rx(d[1]))
    if tag == "yieldfrom":
        return ast.YieldFrom(value=_rx(d[1]))
    if tag == "host":
        return uncanon(d[2])
    raise ValueError(f"cannot raise IR expr tag {d[0]!r}")


def _st(node):
    """Set Store context recursively on assignment targets."""
    for n in ast.walk(node):
        if isinstance(
            n, (ast.Name, ast.Attribute, ast.Subscript, ast.Tuple, ast.List, ast.Starred)
        ):
            n.ctx = ast.Store()
    return node


def _rs(d):  # raise stmt
    tag = d[0]
    if tag == "def":
        body = [_rs(x) for x in d[3]] or [ast.Pass()]
        return ast.FunctionDef(
            name=d[1],
            args=uncanon(d[2][1]),
            body=body,
            decorator_list=[_rx(x) for x in d[4]],
            returns=_rx(d[5]) if d[5] != 0 else None,
        )
    if tag == "class":
        body = [_rs(x) for x in d[3]] or [ast.Pass()]
        return ast.ClassDef(
            name=d[1],
            bases=[_rx(b) for b in d[2]],
            body=body,
            decorator_list=[_rx(x) for x in d[4]],
            keywords=[ast.keyword(arg=k[1], value=_rx(k[2])) for k in d[5]],
        )
    if tag == "ret":
        return ast.Return(value=_rx(d[1]) if d[1] != 0 else None)
    if tag == "assign":
        return ast.Assign(targets=[_st(_rx(t)) for t in d[1]], value=_rx(d[2]))
    if tag == "aug":
        return ast.AugAssign(target=_st(_rx(d[2])), op=_RBIN[d[1]](), value=_rx(d[3]))
    if tag == "ann":
        return ast.AnnAssign(
            target=_st(_rx(d[1])),
            annotation=_rx(d[2]),
            value=_rx(d[3]) if d[3] != 0 else None,
            simple=d[4],
        )
    if tag == "if":
        return ast.If(
            test=_rx(d[1]),
            body=[_rs(x) for x in d[2]] or [ast.Pass()],
            orelse=[_rs(x) for x in d[3]],
        )
    if tag == "for":
        return ast.For(
            target=_st(_rx(d[1])),
            iter=_rx(d[2]),
            body=[_rs(x) for x in d[3]] or [ast.Pass()],
            orelse=[_rs(x) for x in d[4]],
        )
    if tag == "while":
        return ast.While(
            test=_rx(d[1]),
            body=[_rs(x) for x in d[2]] or [ast.Pass()],
            orelse=[_rs(x) for x in d[3]],
        )
    if tag == "try":
        return ast.Try(
            body=[_rs(x) for x in d[1]] or [ast.Pass()],
            handlers=[
                ast.ExceptHandler(
                    type=_rx(h[1]) if h[1] != 0 else None,
                    name=h[2] if h[2] != 0 else None,
                    body=[_rs(x) for x in h[3]] or [ast.Pass()],
                )
                for h in d[2]
            ],
            orelse=[_rs(x) for x in d[3]],
            finalbody=[_rs(x) for x in d[4]],
        )
    if tag == "with":
        return ast.With(
            items=[
                ast.withitem(
                    context_expr=_rx(i[1]), optional_vars=_st(_rx(i[2])) if i[2] != 0 else None
                )
                for i in d[1]
            ],
            body=[_rs(x) for x in d[2]] or [ast.Pass()],
        )
    if tag == "raise":
        return ast.Raise(
            exc=_rx(d[1]) if d[1] != 0 else None, cause=_rx(d[2]) if d[2] != 0 else None
        )
    if tag == "pass":
        return ast.Pass()
    if tag == "break":
        return ast.Break()
    if tag == "continue":
        return ast.Continue()
    if tag == "import":
        return ast.Import(names=[ast.alias(name=n, asname=a if a != 0 else None) for n, a in d[1]])
    if tag == "importfrom":
        return ast.ImportFrom(
            module=d[1] or None,
            level=d[2],
            names=[ast.alias(name=n, asname=a if a != 0 else None) for n, a in d[3]],
        )
    if tag == "global":
        return ast.Global(names=list(d[1]))
    if tag == "nonlocal":
        return ast.Nonlocal(names=list(d[1]))
    if tag == "expr":
        return ast.Expr(value=_rx(d[1]))
    if tag == "del":
        return ast.Delete(targets=[_st(_rx(t)) for t in d[1]])
    if tag == "assert":
        return ast.Assert(test=_rx(d[1]), msg=_rx(d[2]) if d[2] != 0 else None)
    if tag == "host":
        return uncanon(d[2])
    raise ValueError(f"cannot raise IR stmt tag {d[0]!r}")


def ir_to_ast(d) -> ast.AST:
    if d[0] == "module":
        return ast.Module(body=[_rs(s) for s in d[1]], type_ignores=[])
    return _rs(d)


def ir_source(d) -> str:
    """IR -> deterministic Python source. Legacy (v1 pycanon) data falls back
    to the old projection — old store objects stay readable (D-036)."""
    if not is_ir(d):
        from sigil.core.pycanon import host_source

        return host_source(d)
    node = ir_to_ast(d)
    return ast.unparse(ast.fix_missing_locations(node))
