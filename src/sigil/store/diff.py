"""Store diff (v1.1, P3.8): contract impact between two stores/commits."""

from __future__ import annotations

from sigil.store.repo import Store


def store_diff(base: Store, head: Store) -> dict[str, list[str]]:
    """Goal transitions base -> head, keyed by human-readable labels."""
    bg, hg = base.goals(), head.goals()
    bb = {g for g in bg if base.binding(g)}
    hb = {g for g in hg if head.binding(g)}
    ht = {g for g in hg if head.tombstone(g)}

    def label(store: Store, g: str) -> str:
        name = (store.goals().get(g) or {}).get("name", "?")
        return f"{name} {store.display(g)}"

    return {
        "new": sorted(label(head, g) for g in set(hg) - set(bg)),
        "dropped": sorted(label(base, g) for g in set(bg) - set(hg) if g not in ht),
        "bound": sorted(label(head, g) for g in hb - bb),
        "unbound": sorted(label(base, g) for g in (bb - hb) - ht),
        "retired": sorted(label(head, g) for g in ht),
    }
