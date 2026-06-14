# Response to Muninn (Oskar) — disposition

Thank you — both points were right, and both are now addressed. Decisions
recorded as **D-043** (Part 1) and **D-044** (Part 2). Suite: **194 passed, 1
skipped** (was 191 + 1); `ruff check` and `ruff format --check` clean.

## Part 1 — `expand` discarding comments/docstrings — FIXED (accepted in full)

Reproduced exactly: `expand(form="source")` returned the de-commented IR
projection — leading comment, the entire docstring, and inline formatting gone.
You were also right about the cause: comments never survive `ast.parse`,
docstrings are dropped by `_strip_docstring`, and `ir_source` re-emits via
`ast.unparse`, so the original text was unrecoverable from the store.

Implemented your proposed fix:

- The store keeps the **original source bytes** in a sidecar
  (`.sigil/src/<hash>.txt`), keyed by the same full hash. It is never hashed and
  never inside the object — the same store-side rule bindings already follow, so
  identity and every digest are untouched (and all hash-stability properties
  still pass).
- `lift` captures each top-level fn's original span — decorators **and** the
  comment block directly above the `def`, which `ast.get_source_segment` omits
  on its own.
- `expand(form="source")` returns that **verbatim** for lifted, unedited fns
  (comments + docstring + formatting). A fn that exists only as a **patched AST**
  has no record and returns the canonical projection, labeled in-band:
  `# projected from canonical form -- original comments not preserved` — exactly
  the honesty convention you suggested, matching the `?`/`provisional` style.

On your "honest wrinkle": R2's byte-identical-per-hash guarantee is preserved,
and the projection→source transition is **monotonic** (once source is known it
never flips back). Scope is top-level python-lifted fns; the harness already
skips methods/records, and Sigil-native fns keep the lossless printer
projection. Gate test: `tests/harness/test_expand_source_fidelity.py`.

The README line you flagged is reworded: comments/docstrings still don't change
the *hash* (identity is meaning), **but they are no longer discarded** — the
original is kept and returned by `expand`.

## Part 2 — where the savings come from — RELABELED (accepted)

Agreed on all three measurements, and we went one step further than docs:

- **Claim A (terser language):** the printer now emits **ASCII by default**
  (`and <= !=`); glyphs (`∧ ≤ ≠`) are opt-in via `printer.glyph_output()`. They
  cost an extra BPE token each, so emitting them by default was working against
  the token goal. No hash changes (digests are over CBOR, not text). The
  glyph-vs-ASCII token table is now in `docs/cost-model.md`; pin the exact counts
  on your tokenizer with `scripts/measure_costs.py` (the sandbox couldn't reach a
  real tokenizer offline, so we didn't hard-code numbers we couldn't measure).
- **Claim B (compression):** relabeled throughout (`cost-model.md`, README,
  spec) as **working-set / index-card reduction** — "don't carry what you aren't
  using this turn" — and stated plainly that the contracts and effects *add*
  information, the opposite of compression.
- **The real lever:** named explicitly — content addressing makes "unchanged"
  provable, which is the precondition for a stable, prompt-cacheable index
  prefix (R1), plus small structured patch deltas (R2/R3).

Your A/B (Sigil sheet+patch vs. plain-Python-in-cache+patch) is written up in
`cost-model.md` as the experiment that would settle it, pointed at
`scripts/benchmark.py`. We'd genuinely welcome your help designing it — and our
prior is the same as yours: if Sigil wins, the win is the contracts/effects
catching bad edits (fewer retries), not terseness.

— Disposition: both parts landed. See `docs/decisions.md` D-043/D-044,
`CHANGELOG.md`, and `docs/STATUS.md`.
