"""Recursive-descent LL(1) parser for the Sigil text projection.

Grammar: docs/grammar.md (written first, per the sigil-transpile-verify
skill). Glyphs were normalized by the lexer; the parser sees ASCII ops.
"""

from __future__ import annotations

from sigil.core import expr as E
from sigil.core.ast import (
    Contract,
    Effect,
    EffectRow,
    Fn,
    Goal,
    Import,
    Law,
    Module,
    Node,
    Param,
    TypeExpr,
    VerifyClause,
)
from sigil.lang.exprparse import ExprParserMixin
from sigil.lang.lexer import SigilSyntaxError, Tok, tokenize


class Parser(ExprParserMixin):
    def __init__(self, toks: list[Tok]) -> None:
        self.toks = toks
        self.i = 0

    def peek(self, k: int = 0) -> Tok:
        return self.toks[min(self.i + k, len(self.toks) - 1)]

    def next(self) -> Tok:
        t = self.toks[self.i]
        self.i = min(self.i + 1, len(self.toks) - 1)
        return t

    def skip_nl(self) -> None:
        while self.peek().kind == "NL":
            self.next()

    def at(self, kind: str, val: str | None = None) -> bool:
        t = self.peek()
        return t.kind == kind and (val is None or t.val == val)

    def expect(self, kind: str, val: str | None = None, what: str = "") -> Tok:
        t = self.peek()
        if not self.at(kind, val):
            want = val or kind.lower()
            raise SigilSyntaxError(
                f"expected {what or want!r}, found {t.val or t.kind!r}",
                t.line,
                t.col,
                f"insert {want!r} (see docs/grammar.md)",
            )
        return self.next()

    # ---- module structure -------------------------------------------------
    def module(self) -> Module:
        self.expect("KW", "module")
        name = self.expect("NAME").val
        imports: list[Import] = []
        defs: list[Node] = []
        self.skip_nl()
        module_fx = None
        if self.at("FIELD", "fx"):
            self.next()
            module_fx = self.fxrow()
            self.skip_nl()
        while not self.at("EOF"):
            if self.at("KW", "use"):
                self.next()
                mod = self.expect("NAME").val
                while self.at("OP", "."):
                    self.next()
                    mod += "." + self.expect("NAME").val
                imports.append(Import(module=mod, names=[]))
                self.skip_nl()
            elif self.at("KW", "goal"):
                defs.append(self.goal())
                self.skip_nl()
            elif self.at("KW", "fn"):
                defs.append(self.fn())
                self.skip_nl()
            else:
                t = self.peek()
                raise SigilSyntaxError(
                    f"expected 'use', 'goal' or 'fn', found {t.val or t.kind!r}",
                    t.line,
                    t.col,
                    "top level items are use/goal/fn",
                )
        return Module(name=name, imports=imports, defs=defs, fx=module_fx)

    def goal(self) -> Goal:
        self.expect("KW", "goal")
        name = self.expect("NAME").val
        self.expect("OP", "{")
        self.skip_nl()
        intent, output, fx, ack, inputs_ref = "", None, None, None, None
        inputs: list[Param] = []
        laws: list[Law] = []
        verify: list[VerifyClause] = []
        while not self.at("OP", "}"):
            f = self.expect("FIELD", what="goal field (intent/in/out/fx/law/verify/ack)")
            self.skip_nl()
            if f.val == "intent":
                intent = self.expect("STRING").val
            elif f.val == "in":
                inputs = self.params()
            elif f.val == "out":
                output = self.type_expr()
            elif f.val == "fx":
                fx = self.fxrow()
            elif f.val == "law":
                laws.append(Law(text=self.expect("STRING").val))
            elif f.val == "ack":
                ack = self.expect("STRING").val
            elif f.val == "inputs":
                inputs_ref = self.expect("STRING").val
            else:  # verify
                while not self.at("FIELD") and not self.at("OP", "}"):
                    verify.append(VerifyClause(expr=self.expr()))
                    self.skip_nl()
            self.skip_nl()
        self.expect("OP", "}")
        return Goal(
            name=name,
            intent=intent,
            inputs=inputs,
            output=output,
            fx=fx,
            laws=laws,
            verify=verify,
            ack=ack,
            inputs_ref=inputs_ref,
        )

    def fn(self) -> Fn:
        self.expect("KW", "fn")
        name = self.expect("NAME").val
        self.expect("OP", "(")
        params = [] if self.at("OP", ")") else self.params()
        self.expect("OP", ")")
        ret = None
        if self.at("OP", "->"):
            self.next()
            ret = self.type_expr()
        self.skip_nl()
        fx = None
        if self.at("KW", "pure") or self.at("OP", "!"):
            fx = self.fxrow()
            self.skip_nl()
        pre: list[Contract] = []
        post: list[Contract] = []
        while self.at("KW", "pre") or self.at("KW", "post"):
            kw = self.next().val
            if kw == "pre":
                pre.append(Contract(mode="pre", expr=self.expr()))
                self.skip_nl()
            else:
                self.expect("OP", "|")
                binder = self.expect("NAME").val
                self.expect("OP", "|")
                post.append(Contract(mode="post", expr=self.expr(), binder=binder))
            self.skip_nl()
        body = self.block()
        return Fn(name=name, params=params, ret=ret, fx=fx, pre=pre, post=post, body=body)

    def params(self) -> list[Param]:
        out = [self.param()]
        while self.at("OP", ","):
            self.next()
            out.append(self.param())
        return out

    def param(self) -> Param:
        name = self.expect("NAME").val
        ty = None
        if self.at("NAME") or self.at("OP", "["):
            ty = self.type_expr()
        return Param(name=name, ty=ty)

    def type_expr(self) -> TypeExpr:
        if self.at("OP", "["):
            self.next()
            inner = self.type_expr()
            self.expect("OP", "]")
            return TypeExpr(name="[]", args=[inner])
        name = self.expect("NAME", what="type name").val
        args: list[TypeExpr] = []
        if self.at("OP", "["):
            self.next()
            args.append(self.type_expr())
            while self.at("OP", ","):
                self.next()
                args.append(self.type_expr())
            self.expect("OP", "]")
        return TypeExpr(name=name, args=args)

    def fxrow(self) -> EffectRow:
        if self.at("KW", "pure"):
            self.next()
            return EffectRow(effects=[], uncertain=False)
        effects: list[Effect] = []
        while self.at("OP", "!"):
            self.next()
            name = self.expect("NAME", what="effect name").val
            mode = None
            if self.at("OP", "."):
                self.next()
                mode = self.expect("NAME", what="effect mode (read/write)").val
            scope = None
            if self.at("OP", "("):
                self.next()
                scope = self.expect("SCOPE").val
                self.expect("OP", ")")
            uncertain = False
            if self.at("OP", "?"):
                self.next()
                uncertain = True
            effects.append(Effect(name=name, scope=scope, uncertain=uncertain, mode=mode))
        return EffectRow(effects=effects, uncertain=False)

    # ---- statements -------------------------------------------------------
    def block(self) -> E.SigilBlock:
        self.expect("OP", "{")
        self.skip_nl()
        stmts: list[Node] = []
        while not self.at("OP", "}"):
            if self.at("EOF"):
                t = self.peek()
                raise SigilSyntaxError(
                    f"unexpected end of file inside block (line {t.line})",
                    t.line,
                    t.col,
                    "close the block with '}'",
                )
            stmts.append(self.stmt())
            self.skip_nl()
        self.expect("OP", "}")
        return E.SigilBlock(stmts=stmts)

    def stmt(self) -> Node:
        if self.at("KW", "ret"):
            self.next()
            if self.at("OP", "}") or self.peek().kind in ("NL", "EOF"):
                return E.SRet(value=None)
            return E.SRet(value=self.expr())
        if self.at("KW", "if"):
            self.next()
            cond = self.expr()
            then = self.block().stmts
            orelse: list[Node] = []
            if self.at("KW", "else"):
                self.next()
                orelse = self.block().stmts
            return E.SIf(cond=cond, then=then, orelse=orelse)
        if self.at("KW", "for"):
            self.next()
            var = self.expect("NAME").val
            self.expect("OP", "<-")
            it = self.expr()
            return E.SFor(var=var, iter=it, body=self.block().stmts)
        if self.at("KW", "while"):
            self.next()
            cond = self.expr()
            return E.SWhile(cond=cond, body=self.block().stmts)
        t = self.peek()
        target = self.expr()
        if self.at("OP", ":="):
            self.next()
            if not isinstance(target, (E.EName, E.EAttr, E.EIndex)):
                raise SigilSyntaxError(
                    "cannot assign to this expression",
                    t.line,
                    t.col,
                    "assign to a name, attribute, or index (e.g. x := ..., d[k] := ...)",
                )
            return E.SAssign(target=target, value=self.expr())
        return E.SExpr(value=target)


def parse_module(src: str) -> Module:
    return Parser(tokenize(src)).module()


def parse_fxrow(text: str):
    """Parse a bare effect row, e.g. '!fs.read(./cache) !net' or 'pure'
    (used by __sigil_fx__ module budgets and @sigil.bind fx=...)."""
    return Parser(tokenize(text)).fxrow()
