# Response to FIRST_USE_REPORT.md — disposition of every finding

Thanks — this is a model first-use report. Everything actioned in v1.0.1
(CHANGELOG; decisions D-029…D-032). Per-finding:

| Finding | Disposition |
|---|---|
| **BUG: served verify deadlock** | **Fixed** exactly as you diagnosed: `stdin=subprocess.DEVNULL` in `verify/runner.py` (D-029). You were also right about why we missed it — the gate ran in-process; there is now a regression test that drives `verify` through a real stdio `ClientSession` (`tests/harness/test_serve_stdio.py`). The security angle (child could read JSON-RPC traffic) made this worse than a hang. |
| **N1: no MCP path to create goals** | **Fixed**: new `load_module(source)` tool registers goals/fns over pure MCP (D-030). Your scenario B now completes without the CLI round-trip. |
| **N2: store goals invisible to a fresh session** | **Fixed**: the session sheet is seeded with the store's registered goals (+ statuses) at startup — the seed is the initial prefix, so R1 still holds. Discovery no longer needs out-of-band knowledge. |
| **N3: patch paths undocumented for lifted Python** | **Fixed both ways**: `expand(hash, form="canonical")` returns the exact patchable structure, and the `sigil-agent-workflow` skill now documents the real shape (`body.data.body.0.value.right.right`, Constant triples, index 2 = repr). |
| **N4: version 1.27.0 vs 1.0.0** | **Explained + fixed**: "sigil" is a taken PyPI name — an unrelated package shadowed the install in your environment. Distribution renamed `sigil-lang` (import + CLI stay `sigil`), version bumped to 1.0.1 (D-032). |
| **N5: `__sigil_set_insert` on the sheet** | **Fixed**: `__sigil_*` scaffolding filtered from sheets (display only — the effect analyzer still walks it, so no under-reporting; D-031). |
| **N6: full vs display hash mismatch** | **Fixed**: `patch` now returns `{"new_hash": <full>, "display": "#abcd…"}`. |
| **N7: honesty culture** | Kept. This response is part of it: your report found a bug our own gates structurally could not see, because the gate used the in-process path. The new stdio test closes that class of blind spot. |

Suite after fixes: 136 tests green, including two driven through a live
`sigil serve` over stdio.
