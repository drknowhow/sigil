# Sigil `sigil serve` — first real-use report

**Date:** 2026-06-12 · **Tester:** Yep (first external user) · **Method:** drove the
live `sigil serve` MCP server over **stdio**, as a real MCP client would
(`mcp.ClientSession` + `stdio_client`) — *not* the in-process `Harness` shortcut
that `examples/agent-session/run_session.py` uses. Repro scripts: `firstuse/`.

Environment: Windows 11, Python 3.14, fresh `pip install -e ".[dev]"` (clean).
Package reports version **1.27.0** (CHANGELOG says v1.0.0 — see N4).

---

## TL;DR

The read/edit loop (lift → sheet → expand → patch) works well over real MCP and
the error UX is genuinely good. **One real bug**: `verify` deadlocks/times out
when called through `sigil serve` (works fine via CLI and in-process). Root cause
found, one-line fix confirmed (then reverted — yours to apply). Plus a few gaps
where the MCP surface can't reach the product's headline feature (goals/verify).

---

## ✅ What works over the real MCP transport

| Tool | Result |
|---|---|
| `initialize` / `list_tools` | OK — surface is `lift, sheet, expand, patch, verify, session_close` |
| `lift(discount.py)` | `lifted: 3 new` — clean |
| `sheet()` | effect inference correct: `load_config(path) -> ? !fs !unsafe?`, `apply_discount -> ? pure?` |
| `expand(#hash)` | byte-clean source projection of just that fn |
| `patch(#hash, ops)` — bad path | **great error**: `code: bad_path`, op index, failing token, remedy |
| `patch(#hash, ops)` — good path | new hash returned; sheet appends `#87da -> #7cea` (R1 append-only verified). Patch was semantically correct: `price*(1-pct)` → `price*(1-pct/100)` |
| `session_close()` | stats + compacted sheet, as designed |

The patch-by-AST story is real: I changed one subtree and the rest of the
function was untouched by construction. R1/R2/R3 discipline is visibly enforced
by the tool descriptions.

---

## 🐞 BUG — `verify` deadlocks under `sigil serve` (only over MCP)

Same store, same goal (`triple`, buggy impl `n*2`, clause `out == n*3`):

| path | result | time |
|---|---|---|
| in-process `Harness.verify` (your example) | `fail` ✓ | ~10 ms |
| `sigil verify` CLI | `fail` ✓ | ~140 ms |
| **`verify` via `sigil serve` (MCP stdio)** | **`timeout`, killed** ✗ | **10 006 ms** |

`clauses: []`, `detail: "verify exceeded 10.0s and was killed; never binds"` — the
child never gets to evaluating clauses; it hangs at startup.

**Root cause — `src/sigil/verify/runner.py:110`:**

```python
proc = subprocess.run(
    [sys.executable, "-c", script], capture_output=True, text=True, timeout=timeout
)
```

`capture_output=True` redirects stdout/stderr but **leaves stdin inherited**.
Under the stdio MCP transport, the server's stdin *is* the JSON-RPC pipe from the
client, so the verify child inherits that pipe and blocks. From the CLI/in-process
stdin is a normal console, so it never hangs — which is exactly why your examples
never caught it.

**Fix (confirmed):** add `stdin=subprocess.DEVNULL`. With it, served `verify`
returns `fail` in milliseconds. I tested this live, then reverted the edit so your
tree is untouched. (Belt-and-suspenders: consider also isolating handle
inheritance — `close_fds`/`creationflags` on Windows — but DEVNULL alone fixed it.)

This is the single most important finding: the headline "subprocess-isolated,
auto-verifying" loop is currently broken through the very transport you ship
(`sigil serve`), and it's invisible to the in-process test path.

---

## ⚠️ Gaps (design, not bugs) — the goal/verify loop is hard to reach from MCP

- **N1 — No MCP tool registers a goal.** The server exposes lift/sheet/expand/
  patch/verify only. Goals enter via `load_sigil_source` (not exposed) or
  `sigil build` (out-of-band CLI). So through pure MCP, an agent can lift+patch
  Python but cannot create a goal, and `patch` auto-verify just returns
  `"unverified: no goal bound"`. The verify/bind loop — Sigil's headline — is not
  reachable from the MCP surface alone.
- **N2 — Pre-built goals aren't surfaced.** `sheet()` on a fresh serve of a store
  that already contains a registered goal is **empty** (`''`). The session sheet
  only fills from `lift`/`load_sigil_source` calls *this session*; existing store
  goals/fns are invisible, so an agent has no MCP way to *discover* a goal hash to
  verify. (verify *does* work if you already know the hash — once N3 below is
  fixed — but discovery is the missing piece.) Suggest a `goals()`/`store_sheet()`
  tool that lists registered goals + statuses into the sheet.
- **N3 — Patch paths for lifted Python are undocumented/inaccurate.** The
  `sigil-agent-workflow` skill cheat-sheet implies `body.0.value.2`-style paths.
  The real canonical encoding for lifted Python is a positional Python-AST tuple
  `[ClassName, [[field, val], ...]]`, so the actual path was
  `body.data.body.0.value.right.right`. `expand` shows readable *source* but not
  the *schema* an agent needs to build a patch path — so an agent must guess
  against a hidden structure. Either project the canonical paths in `expand`
  output, or correct the skill doc with the real shape.

---

## 📝 Minor notes

- **N4 — Version mismatch.** Package = `1.27.0`; CHANGELOG/README = `v1.0.0`.
- **N5 — Scaffolding leaks onto the sheet.** Lifting the build-generated
  `pricing.py` surfaced an internal helper `__sigil_set_insert(s, x)` as a
  first-class definition. Probably want to filter `__sigil_*`/dunder scaffolding.
- **N6 — Hash display inconsistency.** `patch` returns the full 64-char hash;
  the sheet uses the 4-char `#abcd` display form. An agent has to map between
  them. Returning the display hash (or both) from `patch` would smooth the loop.
- **N7 (positive).** `cost-model.md` correcting the spec's own 10x→5.9x claim and
  the candid `limitations.md` are a real trust signal. Keep that culture.

---

## Suggested priority for the dev

1. **Fix the verify stdio deadlock** (`stdin=DEVNULL`) — it breaks the core promise
   over the shipped transport. Add a test that drives verify through an actual
   stdio `ClientSession`, not the in-process Harness.
2. Decide the **goal-on-MCP** story (N1/N2): expose a register-goal/load-module
   tool and surface existing-store goals into the sheet, or document that goals
   are a build-time-then-serve workflow.
3. Reconcile **patch-path docs** with the real lifted-Python encoding (N3).
4. Cosmetic: N4–N6.

Repro: `python firstuse/drive_serve.py` (read/edit loop + error UX) and
`python firstuse/drive_serve_goal.py` (goal/verify gap + the deadlock).
