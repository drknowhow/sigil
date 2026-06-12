"""Content addressing: digests, short display, prefix-collision escalation."""

from sigil.core.ast import EffectRow, Fn, Param
from sigil.core.hash import DigestNamer, digest_node, fn_digest, short


def _fn(name: str) -> Fn:
    return Fn(
        name=name,
        params=[Param(name="x", ty=None)],
        ret=None,
        fx=EffectRow(effects=[], uncertain=True),
        pre=[],
        post=[],
        body=None,
    )


def test_digest_is_full_sha256_hex() -> None:
    d = digest_node(_fn("a"))
    assert len(d) == 64
    assert all(c in "0123456789abcdef" for c in d)


def test_different_nodes_different_digests() -> None:
    assert digest_node(_fn("a")) != digest_node(_fn("b"))


def test_short_display_default_four_chars() -> None:
    d = digest_node(_fn("a"))
    assert short(d) == "#" + d[:4]
    assert short(d, 8) == "#" + d[:8]


def test_namer_escalates_to_eight_chars_on_prefix_collision() -> None:
    # Brute-force two functions whose digests share a 4-hex-char prefix
    # (16 bits — birthday bound makes this fast).
    seen: dict[str, str] = {}
    pair: tuple[str, str] | None = None
    i = 0
    while pair is None:
        d = fn_digest(f"def g():\n    return {i}\n")
        p = d[:4]
        if p in seen and seen[p] != d:
            pair = (seen[p], d)
        seen[p] = d
        i += 1

    namer = DigestNamer()
    first, second = pair
    assert namer.display(first) == "#" + first[:4]
    # Collision: store escalates to 8 chars, stickily, for everyone.
    assert namer.display(second) == "#" + second[:8]
    assert namer.display(first) == "#" + first[:8]
    # And stays escalated for new, non-colliding entries.
    other = digest_node(_fn("zzz"))
    assert namer.display(other) == "#" + other[:8]


def test_namer_same_hash_twice_is_not_a_collision() -> None:
    namer = DigestNamer()
    d = digest_node(_fn("a"))
    assert namer.display(d) == namer.display(d) == "#" + d[:4]
