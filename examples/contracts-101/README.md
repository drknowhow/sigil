# contracts-101 — `dedupe` with full pre/post (plan §9, example 4)

`dedupe.sg` pins the semantics with three verify clauses: same element set,
no duplicates (`out.len == out.set.len`), never longer. A wrong
implementation (`ret xs`) fails verification and the goal stays
`provisional`; the right one binds. Run: `python3 run_demo.py`
