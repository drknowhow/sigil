# Response to V2_REPORT_addendum.md — proposer-graded validation closed (v2.0.2)

You found the sharpest issue yet: in Tier-3 `propose_contract` the untrusted
party supplied **both** the rule and the single witness, so a false rule could
earn `verified`. Fixed exactly along your headline recommendation.

## The fix (your suggestion #1 + #2 + #3, all shipped)

`propose_contract` no longer validates against the proposer's input. It now:

1. **Generates inputs independently** — the typed property generator when the
   lifted params carry types, and an **edge-biased probe sampler** when they
   don't (your "honest catch": untyped lifted params). The proposer's input is
   included as *one* case and can never bind on its own (#2).
2. **Binds only on zero counterexamples over many independent cases** AND at
   least 8 *applicable* cases. A generated case whose call raises (wrong input
   shape) is **skipped**, not counted as a refutation — so untyped generation
   doesn't false-reject; only a case where the function returns and the clause
   is false is a counterexample.
3. **Makes evidence visible** (#3): the result carries
   `evidence={method, cases_generated, supporting_cases, counterexamples}`, and
   the sheet says `tier-3 verified (40 cases)` or `tier-3 rejected
   (counterexample)` or `tier-3 provisional (thin evidence)` — never a bare
   `verified`.

## Your exact exploit, now (live, v2.0.2)

```
propose 'out == x'  inputs={x:5, lo:0, hi:10}
  -> verify: FAIL  ·  counterexample {x:-100, lo:-2, hi:-1000} -> out=-2
  -> goal status: provisional        (was: verified+bound)

propose 'out == x or out == lo or out == hi'  (the genuinely true property)
  -> verify: PASS over 40 cases  ·  goal status: verified
```

Identical proposer input, opposite outcome from before: the false rule is
refuted by inputs the proposer never chose.

## The honest catch, handled honestly

Generation needs types and lifted Python params often have none. Rather than
guess types or false-reject, untyped params get edge-biased numeric/string/bool
probes; inapplicable shapes are skipped; and if too few cases actually apply
(e.g. a fn that needs a dict), the proposal stays **provisional: insufficient
evidence — propose parameter types or recorded inputs**. That's the truthful
verdict, not a false `verified` and not a false `rejected`.

## Fairness note, seconded

This is the tightening you described, not a redesign: the trust-tier guarantee
("nothing binds without passing something") was always there; v2.0.2 raises the
bar of what "passing" means for the one case where the agent grades its own
work. limitations.md #10 / D-020 updated to note proposals are now validated
against independent inputs.

Suite after the fix: 191 passed + 1 skip; gate tests reproduce your exploit
(`tests/v20/test_propose_validation.py`).
