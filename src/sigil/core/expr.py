"""Sigil expression/statement AST nodes (text-projection bodies, Phase 2).

Registered into core.ast's node registry on import; core.ast.from_data
imports this module lazily when it meets one of these kinds.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sigil.core.ast import _NODE_KINDS, Node


@dataclass(frozen=True)
class ELit(Node):
    lit: str  # int | float | str | bool | none
    val: str  # value text (raw, unescaped for str)


@dataclass(frozen=True)
class EName(Node):
    id: str


@dataclass(frozen=True)
class EAttr(Node):
    value: Node = None
    attr: str = ""


@dataclass(frozen=True)
class ECall(Node):
    func: Node = None
    args: list[Node] = field(default_factory=list)


@dataclass(frozen=True)
class EIndex(Node):
    value: Node = None
    index: Node = None


@dataclass(frozen=True)
class EBin(Node):
    op: str = ""  # or and == != < <= > >= in + - * / // % **  (ASCII canonical)
    left: Node = None
    right: Node = None


@dataclass(frozen=True)
class EUn(Node):
    op: str = ""  # not | -
    value: Node = None


@dataclass(frozen=True)
class EList(Node):
    items: list[Node] = field(default_factory=list)


@dataclass(frozen=True)
class ESet(Node):
    items: list[Node] = field(default_factory=list)  # [] prints as {}


@dataclass(frozen=True)
class EPair(Node):
    key: Node = None
    value: Node = None


@dataclass(frozen=True)
class EMap(Node):
    items: list[EPair] = field(default_factory=list)  # [] prints as {:}


@dataclass(frozen=True)
class EComp(Node):
    """[elt | var <- iter, guard...]"""

    elt: Node = None
    var: str = ""
    iter: Node = None
    guards: list[Node] = field(default_factory=list)


@dataclass(frozen=True)
class SigilBlock(Node):
    stmts: list[Node] = field(default_factory=list)


@dataclass(frozen=True)
class SAssign(Node):
    target: Node = None  # EName | EAttr | EIndex (validated by the parser)
    value: Node = None


@dataclass(frozen=True)
class SRet(Node):
    value: Node | None = None


@dataclass(frozen=True)
class SExpr(Node):
    value: Node = None


@dataclass(frozen=True)
class SIf(Node):
    cond: Node = None
    then: list[Node] = field(default_factory=list)
    orelse: list[Node] = field(default_factory=list)


@dataclass(frozen=True)
class SFor(Node):
    var: str = ""
    iter: Node = None
    body: list[Node] = field(default_factory=list)


@dataclass(frozen=True)
class SWhile(Node):
    cond: Node = None
    body: list[Node] = field(default_factory=list)


_NODE_KINDS.update(
    {
        cls.__name__: cls
        for cls in (
            ELit,
            EName,
            EAttr,
            ECall,
            EIndex,
            EBin,
            EUn,
            EList,
            ESet,
            EPair,
            EMap,
            EComp,
            SigilBlock,
            SAssign,
            SRet,
            SExpr,
            SIf,
            SFor,
            SWhile,
        )
    }
)
