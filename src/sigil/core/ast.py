"""Sigil core AST nodes + plain-data (de)serialization.

The canonical form of a Sigil program is its AST; text is a projection (spec
pillar 1). Nodes serialize to plain JSON-able structures via ``to_data`` /
``from_data``; canonical CBOR encoding and hashing live in ``core.hash``.

Identity rules come from the sigil-canonical-hashing skill: no alpha-renaming
in v1.0 (decisions.md D-003); goal/impl bindings live in the store, never
inside either object.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Any, ClassVar, Union

Data = Union[dict, list, str, int, float, bool, None]  # noqa: UP007 — 3.10-runnable (D-001)


@dataclass(frozen=True)
class Node:
    """Base for all Sigil AST nodes."""

    # Field names whose values are opaque plain data (never recursed into).
    _opaque: ClassVar[frozenset[str]] = frozenset()


@dataclass(frozen=True)
class TypeExpr(Node):
    name: str
    args: list[TypeExpr] = field(default_factory=list)


@dataclass(frozen=True)
class Param(Node):
    name: str
    ty: TypeExpr | None = None


@dataclass(frozen=True)
class Effect(Node):
    """A single effect, e.g. !net(alpaca.markets). ``uncertain`` is the '?'
    marker: a static guess that must never be silenced (CLAUDE.md hard rule)."""

    name: str  # net | fs | rand | clock | env | io | mut | unsafe
    scope: str | None = None
    uncertain: bool = False


@dataclass(frozen=True)
class EffectRow(Node):
    """Empty ``effects`` means pure; row-level ``uncertain`` means 'pure?' —
    statically inferred purity, not proven."""

    effects: list[Effect] = field(default_factory=list)
    uncertain: bool = False


@dataclass(frozen=True)
class Contract(Node):
    mode: str  # "pre" | "post" ('kind' is reserved for the serialization tag)
    expr: Node | str = ""  # parsed expression (Phase 2) or opaque text (lifted)
    binder: str | None = None  # post-condition result binder: post |r| ...


@dataclass(frozen=True)
class VerifyClause(Node):
    expr: Node | str = ""  # parsed expression (Phase 2) or opaque text (lifted)


@dataclass(frozen=True)
class Law(Node):
    text: str


@dataclass(frozen=True)
class HostBlock(Node):
    """A lifted host-language body in canonical form (decisions.md D-005):
    nested tagged lists produced by ``core.pycanon``, hashable as-is."""

    lang: str
    data: Data = None

    _opaque: ClassVar[frozenset[str]] = frozenset({"data"})


@dataclass(frozen=True)
class Fn(Node):
    name: str
    params: list[Param] = field(default_factory=list)
    ret: TypeExpr | None = None
    fx: EffectRow | None = None  # None = undeclared (inferred only)
    pre: list[Contract] = field(default_factory=list)
    post: list[Contract] = field(default_factory=list)
    body: Node | None = None  # HostBlock (lifted) | expr.SigilBlock (parsed)


@dataclass(frozen=True)
class Goal(Node):
    name: str
    intent: str = ""
    inputs: list[Param] = field(default_factory=list)
    output: TypeExpr | None = None
    fx: EffectRow | None = None  # effect *budget*; None = no budget declared
    laws: list[Law] = field(default_factory=list)
    verify: list[VerifyClause] = field(default_factory=list)
    ack: str | None = None  # required when fx contains !unsafe


@dataclass(frozen=True)
class Field(Node):
    name: str
    ty: TypeExpr | None = None


@dataclass(frozen=True)
class Record(Node):
    """Classes-as-records from the lifter (plan Phase 1)."""

    name: str
    fields: list[Field] = field(default_factory=list)
    methods: list[Fn] = field(default_factory=list)


@dataclass(frozen=True)
class Import(Node):
    module: str
    names: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Module(Node):
    name: str
    imports: list[Import] = field(default_factory=list)
    defs: list[Node] = field(default_factory=list)  # Goal | Fn | Record


@dataclass(frozen=True)
class PatchEdit(Node):
    path: str  # dotted path into the target's canonical form
    op: str  # "replace" | "insert" | "delete"
    value: Data = None

    _opaque: ClassVar[frozenset[str]] = frozenset({"value"})


@dataclass(frozen=True)
class Patch(Node):
    target: str  # full hex digest of the node being patched
    edits: list[PatchEdit] = field(default_factory=list)


_NODE_KINDS: dict[str, type[Node]] = {
    cls.__name__: cls
    for cls in (
        TypeExpr,
        Param,
        Effect,
        EffectRow,
        Contract,
        VerifyClause,
        Law,
        HostBlock,
        Fn,
        Goal,
        Field,
        Record,
        Import,
        Module,
        PatchEdit,
        Patch,
    )
}

# 'kind' is the serialization tag; no node may declare a field with that name.
for _cls in _NODE_KINDS.values():
    assert all(_f.name != "kind" for _f in fields(_cls)), _cls


def to_data(node: Node) -> dict:
    """Node -> plain structure with a 'kind' tag. Field order here is
    irrelevant: canonical CBOR sorts keys (core.hash)."""

    def conv(v: Any, opaque: bool) -> Data:
        if opaque:
            return v
        if isinstance(v, Node):
            return to_data(v)
        if isinstance(v, list):
            return [conv(x, False) for x in v]
        if isinstance(v, (str, int, float, bool)) or v is None:
            return v
        raise TypeError(f"unserializable value in AST: {v!r}")

    out: dict = {"kind": type(node).__name__}
    for f in fields(node):
        out[f.name] = conv(getattr(node, f.name), f.name in type(node)._opaque)
    return out


def from_data(data: Data) -> Node:
    """Inverse of ``to_data``. Raises ValueError (cause + remedy) on bad input."""
    if not isinstance(data, dict) or "kind" not in data:
        raise ValueError(
            "Cannot decode AST node: expected a mapping with a 'kind' tag. "
            "Remedy: pass the output of to_data()/canonical store object."
        )
    kind = data["kind"]
    cls = _NODE_KINDS.get(kind)
    if cls is None:
        import sigil.core.expr  # noqa: F401  (registers expression node kinds)

        cls = _NODE_KINDS.get(kind)
    if cls is None:
        raise ValueError(
            f"Unknown AST node kind {kind!r}. Remedy: this object may come from "
            "a newer Sigil version; upgrade sigil or re-lift the source."
        )

    def conv(v: Data, opaque: bool) -> Any:
        if opaque:
            return v
        if isinstance(v, dict) and "kind" in v:
            return from_data(v)
        if isinstance(v, list):
            return [conv(x, False) for x in v]
        return v

    kwargs = {
        f.name: conv(data.get(f.name), f.name in cls._opaque) for f in fields(cls) if f.name in data
    }
    return cls(**kwargs)
