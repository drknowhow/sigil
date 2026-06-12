"""Sigil core AST node tests: construction, to_data/from_data round-trip, equality."""

import pytest

from sigil.core.ast import (
    Contract,
    Effect,
    EffectRow,
    Field,
    Fn,
    Goal,
    HostBlock,
    Import,
    Law,
    Module,
    Param,
    Patch,
    PatchEdit,
    Record,
    TypeExpr,
    VerifyClause,
    from_data,
    to_data,
)


def sample_fn() -> Fn:
    return Fn(
        name="dedupe",
        params=[Param(name="xs", ty=TypeExpr(name="List", args=[TypeExpr(name="T")]))],
        ret=TypeExpr(name="List", args=[TypeExpr(name="T")]),
        fx=EffectRow(effects=[], uncertain=False),
        pre=[],
        post=[Contract(mode="post", expr="set(r) == set(xs) and len(r) <= len(xs)")],
        body=HostBlock(lang="python", data=["Pass", []]),
    )


def sample_module() -> Module:
    goal = Goal(
        name="fetch_prices",
        intent="Daily OHLCV for given tickers; local cache; respect rate limits",
        inputs=[Param(name="tickers", ty=TypeExpr(name="List", args=[TypeExpr(name="Str")]))],
        output=TypeExpr(name="Frame"),
        fx=EffectRow(
            effects=[
                Effect(name="net", scope="alpaca.markets", uncertain=False),
                Effect(name="fs", scope="./cache", uncertain=False),
            ],
            uncertain=False,
        ),
        laws=[Law(text="rate <= 200/min"), Law(text="cache_ttl == 24h")],
        verify=[VerifyClause(expr="out.no_nulls(o,h,l,c)")],
    )
    rec = Record(
        name="Bar",
        fields=[Field(name="ticker", ty=TypeExpr(name="Str"))],
        methods=[sample_fn()],
    )
    return Module(
        name="demo",
        imports=[Import(module="requests", names=[])],
        defs=[goal, sample_fn(), rec],
    )


def test_round_trip_every_node_kind() -> None:
    mod = sample_module()
    patch = Patch(
        target="a" * 64,
        edits=[PatchEdit(path="body.0", op="replace", value=["Pass", []])],
    )
    for node in [mod, patch]:
        data = to_data(node)
        assert from_data(data) == node


def test_to_data_is_plain_jsonable_structure() -> None:
    data = to_data(sample_module())

    def check(x: object) -> None:
        assert isinstance(x, (dict, list, str, int, float, bool, type(None)))
        if isinstance(x, dict):
            for k, v in x.items():
                assert isinstance(k, str)
                check(v)
        elif isinstance(x, list):
            for v in x:
                check(v)

    check(data)
    assert data["kind"] == "Module"


def test_from_data_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError, match="[Uu]nknown"):
        from_data({"kind": "Nonsense"})


def test_effect_row_uncertainty_is_preserved() -> None:
    # 'pure?' (static guess) must survive a round trip — never silenced.
    row = EffectRow(effects=[], uncertain=True)
    assert from_data(to_data(row)) == row
    eff = Effect(name="unsafe", scope=None, uncertain=True)
    assert from_data(to_data(eff)).uncertain is True
