# Sigil v2 field-report addendum — `propose_contract` validates against proposer-chosen input

**Date:** 2026-06-13 · **Tester:** Yep · **Against:** v2.0.1 ·
**Repro:** `firstuse/demo/drive_propose_exploit.py`

## Summary

The Tier-3 `propose_contract` flow lets the connected agent supply **both** the
proposed clauses **and** the single input used to validate them. A passing run is
marked `verified` and bound. Because the proposer chooses the evidence, a *false*
rule can be promoted to `verified` simply by submitting an input on which it
happens to hold. This is the exploitable form of the documented limitation
(`limitations.md` #10 / D-020, "a goal is only as verified as the inputs given") —
acute here because the **untrusted party picks the inputs**.

## Live proof

Lifted, undocumented `clamp(x, lo, hi)` (returns `lo`/`hi`/`x` to keep `x` in
range). Propose the same false rule `out == x` ("the function never changes its
input") with two different proposer-chosen inputs:

```
propose 'out == x'  inputs={x:5,  lo:0, hi:10}   ->  PASS   ← false rule now "verified"
propose 'out == x'  inputs={x:50, lo:0, hi:10}   ->  FAIL
```

`clamp(5,0,10)=5` so `out==x` holds; `clamp(50,0,10)=10` so it doesn't. Identical
rule, opposite verdicts, proposer decides which input to send → a wrong spec binds.

## Root cause

`harness/core.py::propose_contract` (~L356–360):

```python
py_src = ir_source(fn.body.data)
verdict = run_verify_py(self.store, py_src, fn.name, goal, inputs)   # single caller input
result["verify"] = verdict.to_dict()
outcome = "verified" if verdict.status == "pass" else "rejected (stays provisional)"
```

Validation runs once, against the caller-supplied `inputs`. No generation, no
multiple cases, no independent input selection. Validator and evidence-author are
the same (untrusted) party.

## Why it matters

For a human-written goal the human chose the input, so a pass means what they
intended. For an agent *proposal* the agent chose the rule **and** the witness —
it grades its own homework. A `verified` stamp earned this way overstates what is
actually known, and `verified` is indistinguishable on the sheet from a
rule proven over many cases.

## Suggestions (priority order; Sigil already owns most of the parts)

1. **Validate proposals with the property generator, not the proposer's input.**
   v2 already ships it (`sigil verify --gen N` / `run_property_check`; it found
   231/300 counterexamples on the discount goal). Wire it into the propose path
   and `out == x` is refuted in milliseconds. *This single change closes the hole.*
2. **Treat proposer-supplied inputs as untrusted — never bind on them alone.**
   A proposal reaches `verified` only via generated or previously-recorded inputs;
   the agent's own example is a hint, never the proof. Removes the conflict of
   interest structurally.
3. **Make evidence strength visible in status.** `verified (200 generated cases)`
   vs `passed 1 example`, not a flat `verified`. Today the sheet can't distinguish
   a battle-tested rule from a lucky one, and neither can an agent reading it.

## The honest catch (real engineering cost)

Property generation is type-driven, and **lifted Python params are often untyped**
(`clamp`'s parameters carry `ty=null`). So this isn't free — it needs one of:
infer parameter types from body/usage; edge-biased sampling (0, ±1, large,
min/max, empty, negative); or have the proposer also propose types (and verify
those too). That generation-needs-types gap is the actual work.

## Fairness note

The core guarantee still holds — nothing binds without passing *something*, which
already beats trusting an LLM's assertion. This is a **tightening, not a
redesign**: raise the bar of what counts as "passing" for the one case where the
agent grades its own work.
