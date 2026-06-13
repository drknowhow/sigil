# Response to V2_REPORT.md — every finding actioned in v2.0.1

Another sharp report — thank you. Both bugs fixed, all four minors addressed,
and a Windows + 3.13 CI lane added so this class of issue can't reach a user
again. Per-finding:

| Finding | Disposition |
|---|---|
| **Bug 2 — Windows/encoding** (priority 1, as you ranked it) | **Fixed, three ways.** (1) The CLI entrypoint now pins stdout/stderr to UTF-8 (`reconfigure`), so a stock cp1252 console no longer crashes `sigil lift`. (2) All `subprocess.run(..., capture_output=True)` calls in `verify/runner.py` and `lift/rcheck.py` pass `encoding="utf-8", errors="replace"` — no more locale-codec `UnicodeDecodeError 0x97`. (3) Belt-and-suspenders you suggested: the machine-facing sheet footer is now pure ASCII (`~N tok | … | 5.9x smaller`, no `≈ · × —`), and the traceback-guard message lost its em-dash. Gate tests drive `sigil lift` under a forced `PYTHONIOENCODING=cp1252` child and assert the footer is cp1252-encodable. |
| **Bug 1 — invariant binding not persisted** | **Fixed exactly as you diagnosed.** `_reverify_invariants` now mirrors the goal path: on a `pass` verdict it `store.put`s the patched module, re-registers the invariant against it, and `store.bind`s it. The contradiction is gone — a `verify_invariant` after a patch now agrees with the patch's own verdict, and the invariant shows `verified`. Regression test reproduces your exact `enc/dec` sequence. |
| **N — from-pytest extracted 0 drafts** | **Fixed.** The bridge no longer requires a column literally named `expected`; it derives the expected column from the assert's RHS (`assert scale(n) == exp` → expected col `exp`). Your textbook `"n,exp"` table now yields a draft. |
| **N — `migrate` flag UX** | **Fixed.** `sigil migrate` accepts both the positional store and `--store DIR`. |
| **N — failed proposals indistinguishable on the sheet** | **Fixed.** After validation, `propose_contract` appends a status line — `goal <name> tier-3 verified` or `tier-3 rejected (stays provisional)` — so a bound proposal and a rejected one read differently. (R1 holds: the original `proposed` line stays; the outcome is appended.) |
| **Suite red on Python 3.14 + Windows** | **Explained + guarded, not papered over.** You were right it's environmental: the encoding bug (now fixed) accounted for the subprocess failures, and `test_oss_gate` is the expected Python-minor AST hash-drift from our own limitations.md D-002. The two version-sensitive lift goldens now record their generating Python minor and assert byte-exact only on that minor; off-version they assert structure (entry count + names) instead, so a 3.13/3.14 lane reports honest drift, not a false failure. |
| **CI lanes** | **Added** `windows-latest` (3.12) and `ubuntu` 3.13 to the matrix, alongside the existing 3.11/3.12. |

Suite after fixes: 185 passed + 1 skip (Rscript absent here), ruff clean.
Repro your scenarios against v2.0.1 — `drive_v2.py`'s contradiction is gone.
