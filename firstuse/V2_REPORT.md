# Sigil v2.0.0 — first-use report

**Date:** 2026-06-13 · **Tester:** Yep · **Method:** drove the live `sigil serve`
MCP server over stdio (`firstuse/drive_v2.py`) + the new CLI subcommands.
Env: **Windows 11, Python 3.14.4** (note: outside the 3.11/3.12 CI matrix).

## TL;DR

The v2 headline features all work over the real surface: neutral IR, multi-fn
invariants, Tier-3 `propose_contract` (agent-as-proposer), patch-by-snippet, and
the R frontend. **Two real bugs found:** (1) invariant bindings aren't persisted
after a patch — `patch` reports the invariant `pass` but a later
`verify_invariant` regresses to `fail`; (2) a Windows/encoding defect — Sigil
emits `≈`/`—` glyphs and uses locale-codec subprocess capture, which crashes
`sigil lift` on the default Windows console and reddens its own test suite here.
Bug 1 has a confirmed fix.

---

## ✅ What works (validated directly)

| v2 feature | result |
|---|---|
| **Neutral IR (S1)** | `expand(form='canonical')` now returns clean tagged IR — `["ret",["bin","*",["nm","n"],["const","int","2"]]]` — instead of the old `["FunctionDef",[["name",…]]]` Python-AST tuples. Much more patch-friendly. |
| **Multi-fn invariants (P3.9)** | `load_module` registers `invariant round_trip over enc, dec`; `verify_invariant` correctly FAILs on buggy `dec=y-2` and PASSes once fixed. Patching a ranged-over fn *does* trigger auto-reverify (reports pass). |
| **Tier-3 `propose_contract`** | Agent proposes clauses on a lifted fn: `out == n*2` (n=5) → **binds** (pass); `out == n*3` → **fail, stays provisional**. The "can only bind by passing verification, never by assertion" guarantee holds over MCP. Elegant. |
| **`patch_snippet` (v1.1)** | Sent corrected source; Sigil tree-diffed canonical forms, emitted minimal ops, returned new hash + `display`. No path authoring needed. |
| **R frontend (S2)** | `sigil lift stats.R` → `#6b6d analyze(xs) pure?` / `#6b49 load_data(path) !fs.read`. Token-canonical Tier-1 hashing + effect rows work; `read.csv` earns `!fs.read`. (Only works with UTF-8 output — see Bug 2.) |
| **v1.0.1 verify-deadlock fix** | Still solid — every served verify returned in ~40 ms. |

---

## 🐞 Bug 1 — invariant binding is not persisted after a patch

**Repro (`firstuse/drive_v2.py`), all over MCP:**

```
load_module(codec: enc=x+1, dec=y-2 [bug], invariant round_trip over enc,dec)
verify_invariant(round_trip, x=4)         → fail   (dec(enc(4))=3 ≠ 4)   ✓ correct
patch_snippet(dec → y-1, inputs x=4)      → { invariants:[{round_trip: PASS}] }   ← says pass
verify_invariant(round_trip, x=4) AGAIN   → fail   ← CONTRADICTS the line above
```

The patch's auto-reverify says the invariant now passes, but the very next
explicit `verify_invariant` says it still fails. The CHANGELOG promises "passing
binds the invariant to all their impl hashes" — that binding never happens.

**Root cause — `harness/core.py::_reverify_invariants` (~line 259):** it runs
`run_verify_invariant` against an *in-memory* patched module and returns the
verdict, but (unlike the goal path at lines 199–200, which does
`store.put(new_module)` + `register_goal(...)`) it never persists the new module
to the invariant's registration. So the invariant stays registered against the
**pre-patch** module; the next `verify_invariant` re-runs against stale state.

**Fix (confirmed live, then reverted):** in `_reverify_invariants`, on a `pass`
verdict, persist the invariant→patched-module binding, mirroring the goal path:

```python
verdict = run_verify_invariant(self.store, module, d.name, inputs, timeout=timeout)
results.append(verdict)
if isinstance(verdict, dict) and verdict.get("status") == "pass":
    inv_hash = next((gh for gh, e in self.store.goals().items()
                     if e["name"] == d.name and e.get("kind") == "invariant"), None)
    if inv_hash is not None:
        new_mod_hash = self.store.put(module)
        self.store.register_goal(inv_hash, new_mod_hash, d.name, extra={"kind": "invariant"})
```

With this, the second `verify_invariant` returns `pass`. (Consider also a
`store.bind` so the invariant shows `verified`, matching the goal flow.)

---

## 🐞 Bug 2 — Windows / encoding (crashes `sigil lift`; reddens the suite)

Two linked issues, both Windows-default-encoding (cp1252):

1. **CLI output isn't pinned to UTF-8.** `sigil lift stats.R` crashes with
   `'charmap' codec can't encode character '≈'` — the `≈N tok` footer (and
   `—` in messages). `cli.py` reads files as UTF-8 but never reconfigures
   stdout/stderr, so any sheet with `≈`/`—` dies on a stock Windows console.
   Ironically the "you should never see a stack trace" handler hits the same wall
   (its `—` prints as `�`). `PYTHONUTF8=1` works around it.
2. **Subprocess capture uses the locale codec.** `verify/runner.py:182,245,293`
   call `subprocess.run(..., capture_output=True, text=True)` with no `encoding=`,
   so child output is decoded as cp1252. When parent/child encodings disagree you
   get `UnicodeDecodeError: 'utf-8' codec can't decode byte 0x97` (0x97 = cp1252
   em-dash). This is the dominant cause of the failing tests here.

**Fix:** at the CLI entrypoint do `sys.stdout.reconfigure(encoding="utf-8")`
(+stderr), and pass `encoding="utf-8"` to those three `subprocess.run` calls (the
harness scripts emit ASCII/UTF-8, so pinning both ends to UTF-8 is safe). Best
belt-and-suspenders: prefer ASCII fallbacks for `≈`/`—` in machine-facing output.

---

## ⚠️ Suite status on this machine & minor notes

- **Suite is red here: 3–4 failures** (`test_oss_gate`, `test_exit_gate`,
  `test_check_r`, and `test_lift_text_sheet` under UTF-8). But this is **Python
  3.14 + Windows**, outside the 3.11/3.12 CI matrix. Causes look *environmental,
  not v2 logic*: the encoding bug above accounts for the subprocess ones, and
  `test_oss_gate` (requests golden verbatim) is consistent with **Python-3.14 AST
  hash-drift** — exactly limitations.md D-002. Worth a CI lane on 3.13/3.14 and a
  Windows runner so these don't surprise a user; none reflect a feature defect I
  could find by driving the features directly.
- **N (minor) — `from-pytest` extracted 0 drafts** from a textbook
  `@pytest.mark.parametrize("n,exp",[(2,4),(3,6)])` table (no crash, just empty).
  Worth checking what shape it expects, or documenting it.
- **N (minor) — `sigil migrate` takes a positional `[store]`**, not `--store`
  (discoverable only via `migrate --help`).
- **N (cosmetic) — proposed-but-failed contracts** still print
  `goal <name> proposed (tier 3)` on the sheet, indistinguishable from the bound
  one.

## Suggested priority
1. Bug 2 (encoding) — it's the most user-visible: a Windows user's first
   `sigil lift` crashes, and it's reddening your own suite. Cheap fix, big reach.
2. Bug 1 (invariant persistence) — breaks the stated invariant-binding contract.
3. Add a Windows + Python 3.13/3.14 CI lane.
4. Minor: from-pytest extraction, migrate flag UX, sheet labelling of failed proposals.

Repro: `python firstuse/drive_v2.py` (MCP: invariants, propose_contract,
neutral-IR expand, patch_snippet) · `sigil lift firstuse/sample/stats.R` (R, needs
UTF-8 stdout on Windows).
