# Known limitations (honest list — seeded from the roadmap risk register, Phase 1 findings)

1. **Effects on heavily dynamic code.** getattr dispatch, functions passed as values,
   eval, and unknown imports defeat static walking. The lifter emits `!unsafe?` rather
   than guessing — expect it frequently on code with cross-module calls (v1 lifts one
   file at a time; intra-repo imports are "unknown").
2. **Method calls on untracked locals are silent** (decisions.md D-008, narrowed by
   D-025). Origins now survive assignments, annotations, `with`, call results, and local
   helper returns; what remains silent is mutation-style calls on plain locals
   (`seen.add(x)`) and values whose origin enters through containers. The
   `Session.close()` miss from the original spot-check is now flagged `!unsafe?`.
   Roadmap answer: dynamic tracing.
3. **One-directional lifting.** Lift -> edit-via-patches works; lowering back to
   idiomatic Python source is not a v1.0 feature (no bidirectional sync engine).
4. **Property accesses don't propagate effects.** `obj.prop` with an effectful property
   body is invisible without a call site.
5. **Digest stability across Python minor versions is not guaranteed for lifted host
   bodies** (decisions.md D-002): re-lift detects changed hashes; it never drifts silently.
6. **Contract proposer (Tier 3) was cut from v1.0** (the plan's first allowed cut).
   Nothing is ever presented as a verified contract without passing verification.
7. **Token counts in sheet footers are chars/4 estimates**, display-only. Measured
   numbers (real BPE tokenizer) live in docs/cost-model.md — including an honest
   correction of the spec's first-contact claims.
8. **Verify isolation is subprocess + timeout + env-derived flags only.** Network
   blocking during verify is best-effort in v1.0: a malicious implementation could
   make network calls during verification. Do not verify untrusted code on a
   network-sensitive machine; full sandboxing is a v2 candidate.
9. **Effect budgets compare by name, not scope** (D-015): `!net(api.a.com)` admits
   any host in v1.0. Scopes are recorded and displayed, not enforced.
10. **Goal verify inputs are caller-provided** (D-020): a human-written goal is only as
    verified as the inputs given. **Tier-3 *proposals* are stronger (v2.0.2, D-042):**
    they validate against independently generated inputs — the proposer's example is a
    hint, never the proof — and bind only on zero counterexamples over many cases, with
    evidence strength shown on the sheet. Untyped lifted params use edge-biased probing;
    when too few cases apply, the proposal stays provisional rather than claim verified.
