# new-module — write Sigil, run Python (plan §9, example 2)

`prices.sg` holds the spec's `fetch_prices` goal and an implementation written
in Sigil. `sigil build prices.sg` transpiles it to `prices.py` (+ a generated
`test_fetch_prices.py` running the goal's verify clauses; inputs come from a
pytest fixture named `fetch_prices_inputs`).

`over_budget.sg` is the failure demo: the implementation writes a cache file,
but the goal budgets only `!net(api.example.com)` — the build is rejected
statically, naming the violating call chain.

Run the whole story: `python3 run_demo.py`
