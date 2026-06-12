""".sigil/ object store: content addressing, relocation, bindings, escalation."""

import shutil

import pytest

from sigil.core.ast import Law
from sigil.core.hash import digest_node
from sigil.store.repo import Store


def test_put_get_round_trip_and_dedup(tmp_path) -> None:
    store = Store.create(tmp_path)
    node = Law(text="rate <= 200/min")
    h1 = store.put(node)
    h2 = store.put(node)  # idempotent: content-addressed
    assert h1 == h2 == digest_node(node)
    assert store.get(h1) == node
    assert len(list((tmp_path / ".sigil" / "objects").iterdir())) == 1


def test_store_is_relocatable(tmp_path) -> None:
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    store = Store.create(a)
    h = store.put(Law(text="x"))
    shutil.move(str(a / ".sigil"), str(b / ".sigil"))
    moved = Store.open(b)
    assert moved.get(h) == Law(text="x")


def test_resolve_short_full_and_errors(tmp_path) -> None:
    store = Store.create(tmp_path)
    h = store.put(Law(text="abc"))
    assert store.resolve(h) == h
    assert store.resolve("#" + h[:4]) == h
    assert store.resolve(h[:10]) == h
    with pytest.raises(ValueError, match="(?s)not found.*Remedy"):
        store.resolve("#dead")


def test_prefix_collision_escalates_display_stickily(tmp_path) -> None:
    seen: dict[str, str] = {}
    pair = None
    i = 0
    while pair is None:
        h = digest_node(Law(text=str(i)))
        if h[:4] in seen and seen[h[:4]] != h:
            pair = (seen[h[:4]], h)
        seen[h[:4]] = h
        i += 1
    a, b = pair
    texts = {digest_node(Law(text=str(j))): str(j) for j in range(i + 1)}
    (tmp_path / "s2").mkdir()
    store2 = Store.create(tmp_path / "s2")
    store2.put(Law(text=texts[a]))
    assert store2.display(a) == "#" + a[:4]
    store2.put(Law(text=texts[b]))
    assert store2.display(b) == "#" + b[:8]  # escalated
    assert store2.display(a) == "#" + a[:8]  # sticky, store-wide
    reopened = Store.open(tmp_path / "s2")
    assert reopened.display(a) == "#" + a[:8]  # persisted


def test_binding_lifecycle(tmp_path) -> None:
    store = Store.create(tmp_path)
    g = store.put(Law(text="pretend-goal"))
    impl = store.put(Law(text="pretend-impl"))
    store.register_goal(g, module_hash=None, name="g")
    assert store.status(g) == "provisional"
    assert "provisional" in store.describe_goal(g)
    store.bind(g, impl)
    assert store.status(g) == "verified"
    desc = store.describe_goal(g)
    assert "verified" in desc and store.display(impl) in desc
