# Decisions log

Running log of design decisions not settled by the spec/plan, per CLAUDE.md.
Format: D-NNN, date, decision, rationale, revisit-when.

---

**D-001** (2026-06-11) — **Dev environment runs Python 3.10; project standard stays 3.11+.**
The Cowork sandbox has only 3.10 and no root. Code is written to the 3.11+ standard but
avoids 3.11-only syntax (no `except*`, no 3.12 type-param syntax) so the suite runs in the
sandbox via `PYTHONPATH=src`. `pyproject.toml` pins `requires-python = ">=3.11"`; CI matrix
is 3.11/3.12 as the plan requires. Revisit: when CI runs on real 3.11/3.12, confirm goldens.

**D-002** (2026-06-11) — **Digest stability is guaranteed within a store, not across Python
minor versions, for lifted host bodies.** Lifted Python bodies are canonicalized from
`ast` structures, whose node shapes can shift between Python minor versions. The plan's
idempotency rule ("re-lift detects changed hashes") already handles this: a version bump
shows up as changed hashes on re-lift, never as silent drift. Golden digests are pinned to
the version that generated them and regenerated (with a log entry) on interpreter upgrades.
Revisit: if cross-version stability becomes a requirement, add a version-normalizing
canonical layer (v2 candidate).

**D-003** (2026-06-11) — **No alpha-renaming in v1.0 canonical form** (per
sigil-canonical-hashing skill rule 4). Parameter names are part of identity. Unison-style
alpha-equivalence recorded here as a v2 candidate.

**D-004** (2026-06-11) — **CBOR canonical encoding = cbor2 `canonical=True`** (RFC 7049
canonical: definite lengths, length-first sorted map keys). The skill says "sorted map
keys"; RFC canonical ordering satisfies determinism, which is the load-bearing property.
JSON debug dumps use `sort_keys=True`. Revisit: only if a second CBOR implementation must
interoperate byte-for-byte.

**D-005** (2026-06-11) — **Lifted host bodies are stored as a single `HostBlock` node**
carrying the canonicalized host-AST structure (nested tagged lists), not as a full Sigil
expression tree. Tier 1 needs identity + patchability, not Sigil semantics, for lifted
code; the Sigil expression grammar arrives in Phase 2 for code *written* in Sigil. Simpler
option chosen per CLAUDE.md. Revisit: Phase 2, if patches need finer-grained host-body
addressing than HostBlock paths provide.

**D-006** (2026-06-11) — **`mcp` dependency lives in a `[harness]` extra**, not core deps,
so `sigil lift`/`build` installs stay stdlib+cbor2. Plan lists mcp/fastmcp as expected;
making it an extra is the smaller footprint and changes nothing for Phase 4.

**D-007** (2026-06-11) — **PoC ast.dump digests retired; goldens generated once from the
canonical-CBOR form** (per the sigil-canonical-hashing skill gotcha). Goldens:
`tests/golden/demo_module.sheet`, `tests/golden/requests.sheet` (requests 2.34.2 snapshot,
302 entries — includes a real 4-char prefix collision, exercising the 8-char escalation).

**D-008** (2026-06-11) — **Method calls on untracked local values are silent in Tier 2.**
Emitting !unsafe? on every such call (`seen.add(x)`, `r.append(...)`) would drown sheets in
noise and destroy the over-report budget; the PoC made the same trade. Found concretely in
the requests spot-check (`Session.close` -> `v.close()` releases connection pools: a true
!net missed). Mitigations in v1.0: origin tracking through assignments/annotations/with/
call-results (catches the common cases); honest documentation in limitations.md. Real
answer: dynamic tracing (roadmap, v2 candidate). Under-report rate on the hand-labeled
OSS sample: 1/30 after the case_031 fix — within the <10% Phase 1 gate.

**D-009** (2026-06-11) — **os.path I/O predicates are !fs, overriding the skill's
"os.path is pure" shorthand.** `os.path.exists/isfile/getsize/...` read the filesystem;
the shorthand only holds for the string-manipulation subset. Prime directive (zero
under-reporting) outranks the literal rule text. Fixture: case_031. Also refined:
urllib.parse / http.cookiejar / http.cookies are pure (were !net — pure over-report noise).

**D-010** (2026-06-11) — **Overloaded defs (`@overload`) produce one sheet entry per def,
all sharing the implementation's effect row.** Duplicate-name handling (last-def-wins
identity vs. per-overload identity) deferred until the store lands in Phase 3.

**D-011** (2026-06-12) — **The spec's `⊑` (subsequence) operator is not in the v1.0
core grammar**; it was illustrative. Order-preservation contracts can be expressed via
library predicates when the verify runner lands. v2 candidate.

**D-012** (2026-06-12) — **`{}` is the empty Set; `{:}` the empty Map** — keeps the
spec's `s := {}` dedupe idiom literal while staying LL(1).

**D-013** (2026-06-12) — **Generated goal-test modules take inputs from a pytest fixture
named `<goal>_inputs`** and expose `run_verify(out, **inputs)` for direct use. The verify
RUNNER (subprocess, cached) is Phase 3; these modules are its substrate.

**D-014** (2026-06-12) — **Newlines terminate statements, goal fields, contracts and
verify clauses** (insignificant inside parens/brackets). Found by the round-trip property:
fully insignificant newlines make `x := 0` followed by `-1` ambiguous (binary minus).
LL(1) preserved; grammar.md updated.

**D-015** (2026-06-12) — **Effect budgets compare by effect NAME; scopes are carried but
not enforced in v1.0.** Static analysis cannot recover hosts/paths reliably; pretending
otherwise would be false confidence. Scope enforcement: v2 candidate (dynamic tracing).

**D-016** (2026-06-12) — **A goal binds to the same-name fn in its module** until the
Phase 3 store provides hash-based goal<->impl bindings.

**D-017** (2026-06-12) — **Std idiom mapping in the transpiler:** `.len` -> len(),
`.set` -> set(), `.keys` -> list(.keys()), `Set.insert` -> __sigil_set_insert helper
(add-if-absent returning bool, as the spec's dedupe requires). Unknown type names emit
no Python hint. Generated code carries a "do not edit" header.

**D-018** (2026-06-12) — **Store layout:** `.sigil/{objects,vcache,index.json,config.json}`
with all paths relative (relocatable, plan §10). Bindings and the goals registry live in
index.json; verdicts in vcache keyed `<goal>-<impl>`. Single-writer assumption in v1.0;
concurrent-writer locking is a v2 candidate.

**D-019** (2026-06-12) — **Pass and fail verdicts are cached forever (hashes are
immutable); timeout and error verdicts are NOT cached** — they describe the environment
(slow machine, missing import), not the code, so re-running must re-execute.

**D-020** (2026-06-12) — **Verify inputs come from the caller** (`--inputs file.json` /
API argument), not from the store. Recording representative inputs alongside goals is a
Tier-3/v2 concern; guessing inputs silently would violate the no-false-confidence rule.

**D-021** (2026-06-12) — **Patch paths address the plain-data form** (to_data dicts,
list indices, canonical host-AST field names), op set {replace, insert, delete}. The
skill's `at body.comprehension.guard:` notation was illustrative; dotted data paths are
simpler and unambiguous. Malformed ops report op index + failing token + code=bad_path.

**D-022** (2026-06-12) — **Patch auto-verify needs inputs for goals that declare in:**
(D-020 applies). Without them, patch returns
"unverified: inputs required — call verify(goal, inputs)" rather than guessing. Goals
with no inputs verify automatically on every patch.

**D-023** (2026-06-12) — **The Phase 4 live-session gate ran in scripted form**
(tests/harness/test_exit_gate.py + examples/agent-session/): sheet-only reading, seeded
bug fixed via one patch op, auto-verify binds, R1 prefix-stability asserted, zero file
reads/writes. A live Claude Code session against `sigil serve` is the user-facing
validation and is documented in the harness guide; the harness exposes identical calls.

**D-024** (2026-06-12) — **Test packages gained __init__.py** to break a pytest basename
collision (two test_exit_gate.py files in different phase dirs).

**D-025** (2026-06-12) — **Return-taint propagation added to the analyzer** (rounds over
the module so a helper returning a Path-like or dynamic value taints its callers' use).
Found while lifting examples/lift-legacy: `read_cache` missed !fs because the Path died
at the `cache_path()` boundary; `dispatch` missed dynamic dispatch through `handler_for`.
Fixtures case_032/case_033 written first, per protocol. Golden tests/golden/requests.sheet
regenerated: 10 rows improved, including `HTTPAdapter.close` pure? -> !unsafe? — part of
the D-008 spot-check miss is now honestly flagged. Benchmark: 33 fixtures, zero
under-reports, 2.6% over-report.

**D-026** (2026-06-12) — **Tier-3 contract proposer cut from v1.0** — the plan's first
allowed cut (§11), taken to land Phase 5 fully. lift/contracts.py does not exist; nothing
in the system presents unverified contracts as specs (the trust-tier invariant holds
trivially). v1.1 candidate, gated on the roadmap's 60% validation target.

**D-027** (2026-06-12) — **Measured token numbers replace the spec's estimates**
(docs/cost-model.md, scripts/measure_costs.py, Claude BPE offline; sigil-quality-gates:
"the spec is marketing until measured"). First-contact reduction on requests 2.34.2 is
5.9x, not the spec's eyeballed 10x+; the iteration-turn economics (R1 cached sheet +
expand-on-demand + patches) are where the larger claim holds and are measured in the
agent-session example. Sheet footers stay chars/4 and say so.

**D-028** (2026-06-12) — **v1.0.0 cut.** Clean-venv install + console script validated
(on the sandbox via --ignore-requires-python, D-001 applies); CI enforces the 3.11/3.12
matrix and an 85% coverage floor on core/lift/transpile (measured 92%).


**D-029** (2026-06-12) — **Verify subprocesses run with stdin=DEVNULL.** Found by the
first external user (firstuse report): under stdio MCP transport, the inherited stdin IS
the client's JSON-RPC pipe — served verify deadlocked into its timeout, and untrusted
code could in principle read client traffic. Invisible to in-process tests; regression
test now drives a real stdio ClientSession (tests/harness/test_serve_stdio.py).

**D-030** (2026-06-12) — **Tool contract extended (per the frozen-contract rule):**
`load_module(source)` added so goals are creatable over pure MCP (firstuse N1); a new
session seeds its sheet with the store's registered goals (N2 — discovery; the seed is
the initial prefix, R1 append-only holds after); `expand` gains form="canonical" (N3 —
the patchable data form, so agents derive paths instead of guessing).

**D-031** (2026-06-12) — **Lift entries skip `__sigil_*` scaffolding** (firstuse N5).
Display-level only: the effect analyzer still walks them in the call graph, so no
under-reporting. Patch results carry both full and display hashes (N6).

**D-032** (2026-06-12) — **Distribution renamed to `sigil-lang`** (firstuse N4): the
PyPI name "sigil" belongs to an unrelated project (their v1.27.0 shadowed our install
during external testing). Import package and console script remain `sigil`.

**D-033** (2026-06-12) — **Post-1.0 roadmap triaged from the first user's
UPGRADE_PROPOSALS.md** (firstuse/). Accepted with modifications: effect modes +
module budgets, @sigil.bind lifter-frontend decorator, patch-by-snippet (selector
DSL rejected as subsumed), unbind tombstones, sheet diff (v1.1); recorded inputs →
sigil check CI gate → watch → property generation (v1.2); language-neutral IR + R
frontend gated behind Python depth, IR flagged as a one-way door requiring a store
migration tool (v2). Full argument: firstuse/PROPOSALS_RESPONSE.md;
plan: docs/roadmap-next.md. Nothing here changes v1.0.1 behavior.


**D-034** (2026-06-12) — **v1.1 node-shape change, batched.** Effect.mode, Module.fx and
Goal.inputs_ref were added in one release so Sigil-node hashes break once, not three
times (lifted-code digests unaffected). Mode semantics: an unmoded effect is the
superset (read+write collapse to it; budgets granting `!fs` admit both; budgets granting
`!fs.read` reject writes). Inferred unmoded effects require an unmoded grant — the
analyzer only narrows to a mode on positive evidence (open() literal mode, os.path
predicate table, Path method names), never by guess. Goldens regenerated (7 rows in
requests.sheet gained modes). Budget messages are mode-precise; the 1.0 golden message
test updated accordingly.


**D-035** (2026-06-12) — **v1.2 loop closure.** Recorded inputs resolve in order:
registry inline -> registry inputs_file -> goal.inputs_ref (store-root relative).
Verdict cache key extended to (goal, impl, inputs-digest) — the v1.0 key silently
conflated different inputs; old vcache entries are orphaned, not migrated (re-verify is
cheap and honest). `check` re-derives bind state by re-verification, never trusting a
committed verdict (forgeability). Property generation is stdlib-seeded (not hypothesis)
for runtime-dependency-free determinism; generators exist only for fully-typed goals.
Crash-in-impl became structured per-case 'fail' (was whole-run 'error'); isolation
unchanged.


**D-036** (2026-06-12) — **The IR one-way door, softened.** New lifts hash to the
language-neutral IR; v1 (pycanon-shaped) store objects stay readable forever via the
legacy path in ir_source, so `sigil migrate` is a survey + format bump, not a breaking
rewrite. Python signatures stay host-wrapped inside `["def", …, ["pyargs", …]]` —
argument-shape neutrality wasn't worth lying about Python's calling conventions; R uses
its own `["rargs", names]`. Sheet digests for lifted code changed once (goldens regen).

**D-037** (2026-06-12) — **R Tier-1 is token-canonical, not AST-canonical.** A real R
parser (NSE, promises) is not v2.0 scope; normalized token sequences give honest
content-addressing and survive comments/whitespace. Effect rows are token-rule based and
deliberately noisy with !unsafe? (library/source/do.call/eval). The reproducibility
wedge — `analyze(seed=42) ≡ #hash` — runs through Rscript with deparse-stable hashing.

**D-038** (2026-06-12) — **Tier 3 ships as propose/validate, not an embedded LLM.** The
connected agent is the proposer; the harness enforces the trust tier mechanically:
proposals register provisional, bind only by passing verification. The pytest bridge
emits reviewable drafts (never auto-registered) — parametrize tables only, by design.
