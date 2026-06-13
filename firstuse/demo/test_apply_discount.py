"""Generated from goal 'apply_discount' (module pricing).

Inputs come from a pytest fixture named apply_discount_inputs (docs/decisions.md D-013).
"""

def run_verify(out, price, pct):
    """Evaluate every verify clause; returns [(clause_text, passed)]."""
    results = []
    results.append(('out ≥ 0', bool((out >= 0))))
    results.append(('out ≤ price', bool((out <= price))))
    return results


def test_apply_discount(apply_discount_inputs):
    from pricing import apply_discount
    out = apply_discount(**apply_discount_inputs)
    checks = run_verify(out, **apply_discount_inputs)
    failures = [c for c, ok in checks if not ok]
    assert not failures, "verify failed: " + repr(failures)
