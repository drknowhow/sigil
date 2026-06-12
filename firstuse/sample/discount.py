"""Fresh sample for first-use test of `sigil serve` (not the canned example)."""


def apply_discount(price, pct):
    # BUG: pct is a percentage (e.g. 20 for 20%), so this should be
    # price * (1 - pct / 100). As written it treats pct as a fraction.
    return price * (1 - pct)


def load_config(path):
    import json

    with open(path) as f:
        return json.load(f)


def total_after_tax(items, rate):
    subtotal = sum(i["price"] for i in items)
    return subtotal * (1 + rate)
