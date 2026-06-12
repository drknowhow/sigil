# lift-legacy — a flask-style app lifted (plan §9, example 1)

`webapp.py` is a deliberately effect-rich legacy module (network, fs cache,
env config, clock, randomness, logging, one dynamic-dispatch trap).

Lift it: `sigil lift webapp.py` — every function gets a content hash and an
inferred effect row; the dynamic dispatch is honestly marked `!unsafe?`.

Measured context costs (real tokenizer, see docs/cost-model.md and
scripts/measure_costs.py): webapp.py is 767 tokens; its digest sheet is 300
tokens (2.6x smaller). On a real repo (requests 2.34.2) the measured
reduction is 5.9x. Reductions compound on iteration turns: unchanged
definitions are never re-sent — only their digest lines (R1/R2).
