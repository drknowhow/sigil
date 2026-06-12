---
name: sigil-canonical-hashing
description: Canonicalization and content-addressing rules for Sigil's core AST. ALWAYS consult this skill before writing or modifying anything in src/sigil/core/ (ast.py, hash.py), the lifter's canonical form, digest generation, serialization, or any test involving hash stability. Also use when debugging "digest changed unexpectedly" issues or designing patch identity.
---

# Sigil Canonicalization & Hashing

Everything in Sigil builds on one property: **semantically identical code always hashes identically; semantically different code never silently collides.** Get this wrong and digests, patches, caching, and verification all rot.

## Canonical form rules (apply in this order)
1. Parse to AST; discard all formatting, comments, and docstrings (docstring = leading string-constant Expr in a body; if removal empties a body, insert Pass).
2. Strip position info (lineno/col/end_*) and any field that doesn't change semantics.
3. Normalize equivalent literal spellings (0x10 vs 16 hash identically because the parsed value is hashed, not the text). No constant folding.
4. Do NOT alpha-rename in v1.0 (Unison-style alpha-equivalence is out of scope — record as a v2 candidate in docs/decisions.md). Parameter names are part of identity.
5. Serialize canonical AST to CBOR with **sorted map keys** and definite-length encoding only. JSON debug dump must also sort keys.

## Hashing
- sha256 over the canonical CBOR bytes.
- Display form: `#` + first 4 hex chars. On prefix collision within a store, escalate that store to 8 chars (store-level setting, sticky). Full hash is always what is persisted; short form is display-only.
- A goal's identity and an implementation's identity are separate hashes; the binding `(goal_hash, impl_hash, verified_at)` lives in the store, never inside either object.

## The load-bearing tests (write these FIRST)
```python
# tests/properties/test_hash_stability.py — hypothesis-driven
# 1. Formatting noise: insert comments/blank lines/whitespace via text mutation -> hash unchanged
# 2. Docstring add/remove/edit -> hash unchanged
# 3. Any single AST node mutation (rename var, change constant, swap operator) -> hash CHANGES
# 4. serialize(parse(x)) round-trips byte-identically; hash(deserialize(serialize(a))) == hash(a)
```
Property 3 matters as much as 1-2: a canonicalizer that over-normalizes will merge distinct programs.

## Gotchas observed in the PoC (sigil_lift.py)
- `ast.unparse` -> reparse is used to detach a clean copy; keep that trick, but hash the canonical CBOR, not unparsed text (text is renderer-dependent).
- `ast.dump(...)` was the PoC stopgap — replace with the CBOR canonical form; keep a golden test pinning PoC digests only until Phase 0 lands, then regenerate goldens once, with a decisions.md entry.
