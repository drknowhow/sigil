# Language guide — goals, contracts, effects

Full grammar: grammar.md. The AST is canonical; text is a projection.

## Goals: the human's half

```sigil
goal fetch_prices {
  intent: "Daily OHLCV for the given tickers from the demo API"
  in: tickers [Str], start Str, end Str
  out: Map
  fx: !net(api.example.com)
  law: "rate <= 200/min"
  verify:
    out.keys.set == tickers.set
}
```

`intent` is for humans; `verify` is the acceptance test (executable);
`fx` is a *budget* — the implementation may use at most these effects, checked
statically at build time. `law` lines are recorded constraints (informational
in v1.0). A goal budgeting `!unsafe` must carry an `ack: "<reason>"`.

## Implementations: the machine's half

```sigil
fn dedupe(xs [Int]) -> [Int]
  pure
  post |r| r.set == xs.set and r.len <= xs.len
{
  s := {}
  ret [x | x <- xs, s.insert(x)]
}
```

`pure` is part of the signature — adding an `!fs` call is a build error, not a
review catch. `pre`/`post` compile to assertions in dev builds and vanish in
release. `|r|` binds the result in postconditions.

## Effects

`pure`, `!net(host)`, `!fs(path)`, `!rand`, `!clock`, `!env`, `!io`, `!mut`,
`!unsafe`. Rows propagate through the call graph; budgets are compared by
effect name (scope enforcement is v2 — decisions.md D-015). Violations name
the call chain: `fetch_prices -> save_cache: open requires !fs; budget allows !net(...)`.

## Pocket reference

Statements end at end-of-line. `:=` assigns. `{}` is the empty Set, `{:}` the
empty Map (D-012). Comprehension: `[x * 2 | x <- xs, x > 0]`. The printer emits
ASCII operators `and or not <= >= !=` (canonical — one BPE token each); the
glyph spellings `∧ ∨ ¬ ≤ ≥ ≠` are accepted on input and available opt-in (D-044).
Idioms: `.len`, `.set`, `.keys`, `Set.insert` (D-017). Comments: `-- ...`.

## Invariants (v2.0)

```sigil
invariant round_trip {
  in: x Int
  over: enc, dec
  verify:
    dec(enc(x)) == x
}
```

A property over multiple functions: patching ANY fn in `over:` re-verifies it;
passing binds the invariant to all their impl hashes.

The binding between a goal and its implementation lives in the `.sigil` store,
created by verification — never asserted by hand. Module-wide budgets
(`fx:` after the module header, or `__sigil_fx__ = "!fs.read"` in Python)
constrain every fn at once; effect modes (`!fs.read` / `!fs.write`, `!db`)
make budgets precise.
