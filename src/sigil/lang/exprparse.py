"""Expression parsing (precedence climbing) — mixin for lang.parser.Parser.

Split from parser.py to honor the 400-line file limit (CLAUDE.md). Grammar:
docs/grammar.md. The mixin relies on the host class's token helpers
(peek/next/at/expect) and produces sigil.core.expr nodes.
"""

from __future__ import annotations

from sigil.core import expr as E
from sigil.core.ast import Node
from sigil.lang.lexer import SigilSyntaxError

CMP_OPS = {"==", "!=", "<", "<=", ">", ">=", "in"}
ADD_OPS = {"+", "-"}
MUL_OPS = {"*", "/", "//", "%"}


class ExprParserMixin:
    def expr(self) -> Node:
        return self.or_expr()

    def or_expr(self) -> Node:
        left = self.and_expr()
        while self.at("KW", "or"):
            self.next()
            left = E.EBin(op="or", left=left, right=self.and_expr())
        return left

    def and_expr(self) -> Node:
        left = self.not_expr()
        while self.at("KW", "and"):
            self.next()
            left = E.EBin(op="and", left=left, right=self.not_expr())
        return left

    def not_expr(self) -> Node:
        if self.at("KW", "not"):
            self.next()
            return E.EUn(op="not", value=self.not_expr())
        return self.cmp_expr()

    def cmp_expr(self) -> Node:
        left = self.add_expr()
        t = self.peek()
        if (t.kind == "OP" and t.val in CMP_OPS) or (t.kind == "KW" and t.val == "in"):
            self.next()
            return E.EBin(op=t.val, left=left, right=self.add_expr())
        return left

    def add_expr(self) -> Node:
        left = self.mul_expr()
        while self.at("OP", "+") or self.at("OP", "-"):
            op = self.next().val
            left = E.EBin(op=op, left=left, right=self.mul_expr())
        return left

    def mul_expr(self) -> Node:
        left = self.pow_expr()
        while self.peek().kind == "OP" and self.peek().val in MUL_OPS:
            op = self.next().val
            left = E.EBin(op=op, left=left, right=self.pow_expr())
        return left

    def pow_expr(self) -> Node:
        left = self.unary()
        if self.at("OP", "**"):
            self.next()
            return E.EBin(op="**", left=left, right=self.pow_expr())
        return left

    def unary(self) -> Node:
        if self.at("OP", "-"):
            self.next()
            return E.EUn(op="-", value=self.unary())
        return self.postfix()

    def postfix(self) -> Node:
        e = self.primary()
        while True:
            if self.at("OP", "("):
                self.next()
                args: list[Node] = []
                if not self.at("OP", ")"):
                    args.append(self.expr())
                    while self.at("OP", ","):
                        self.next()
                        args.append(self.expr())
                self.expect("OP", ")")
                e = E.ECall(func=e, args=args)
            elif self.at("OP", "["):
                self.next()
                idx = self.expr()
                self.expect("OP", "]")
                e = E.EIndex(value=e, index=idx)
            elif self.at("OP", "."):
                self.next()
                e = E.EAttr(value=e, attr=self.expect("NAME").val)
            else:
                return e

    def primary(self) -> Node:
        t = self.peek()
        if t.kind == "NUMBER":
            self.next()
            return E.ELit(lit="float" if "." in t.val else "int", val=t.val)
        if t.kind == "STRING":
            self.next()
            return E.ELit(lit="str", val=t.val)
        if t.kind == "KW" and t.val in ("true", "false"):
            self.next()
            return E.ELit(lit="bool", val=t.val)
        if t.kind == "KW" and t.val == "none":
            self.next()
            return E.ELit(lit="none", val="none")
        if t.kind == "NAME":
            self.next()
            return E.EName(id=t.val)
        if self.at("OP", "("):
            self.next()
            e = self.expr()
            self.expect("OP", ")")
            return e
        if self.at("OP", "["):
            return self.bracket()
        if self.at("OP", "{"):
            return self.brace()
        raise SigilSyntaxError(
            f"expected an expression, found {t.val or t.kind!r}",
            t.line,
            t.col,
            "see docs/grammar.md for expression syntax",
        )

    def bracket(self) -> Node:
        self.expect("OP", "[")
        if self.at("OP", "]"):
            self.next()
            return E.EList(items=[])
        first = self.expr()
        if self.at("OP", "|"):
            self.next()
            var = self.expect("NAME").val
            self.expect("OP", "<-")
            it = self.expr()
            guards: list[Node] = []
            while self.at("OP", ","):
                self.next()
                guards.append(self.expr())
            self.expect("OP", "]")
            return E.EComp(elt=first, var=var, iter=it, guards=guards)
        items = [first]
        while self.at("OP", ","):
            self.next()
            items.append(self.expr())
        self.expect("OP", "]")
        return E.EList(items=items)

    def brace(self) -> Node:
        self.expect("OP", "{")
        if self.at("OP", "}"):
            self.next()
            return E.ESet(items=[])
        if self.at("OP", ":"):
            self.next()
            self.expect("OP", "}")
            return E.EMap(items=[])
        first = self.expr()
        if self.at("OP", ":"):
            self.next()
            pairs = [E.EPair(key=first, value=self.expr())]
            while self.at("OP", ","):
                self.next()
                k = self.expr()
                self.expect("OP", ":")
                pairs.append(E.EPair(key=k, value=self.expr()))
            self.expect("OP", "}")
            return E.EMap(items=pairs)
        items = [first]
        while self.at("OP", ","):
            self.next()
            items.append(self.expr())
        self.expect("OP", "}")
        return E.ESet(items=items)
