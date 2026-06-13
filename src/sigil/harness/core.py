"""Harness state: the digest/expand/patch/verify loop over a .sigil store.

Transport-independent (server.py wires this to FastMCP). Behavior rules come
from the sigil-harness-rules skill: R1 append-only sheet (context.py), R2
expand-over-regenerate, R3 verify-before-display with small structured
failure feedback.
"""

from __future__ import annotations

from pathlib import Path

from sigil.core.ast import Fn, Goal, HostBlock, Invariant, Module, Node, from_data, to_data
from sigil.core.ir import ir_source
from sigil.core.patch import apply_ops, diff_data
from sigil.harness.context import SessionSheet
from sigil.lang import printer
from sigil.lang.parser import parse_module
from sigil.lift.python import lift_source
from sigil.store.repo import Store
from sigil.verify.runner import run_verify


class Harness:
    def __init__(self, root: Path | str) -> None:
        self.store = Store.create(Path(root))
        self.sheet_log = SessionSheet()
        self._lift_index: dict[tuple[str, str], str] = {}  # (path, name) -> store hash
        self._lifted: dict[str, str] = {}  # name -> store hash
        # N2 (firstuse): a session over an existing store starts with the
        # registered goals on the sheet — discovery without out-of-band CLI.
        # Seed lines form the initial prefix; R1 (append-only) holds after.
        for gh in sorted(self.store.goals()):
            self.sheet_log.append(self.store.describe_goal(gh))

    # ---- helpers -----------------------------------------------------------
    def _disp(self, full: str) -> str:
        return self.store.display(full)

    # ---- lift ----------------------------------------------------------------
    def lift(self, path: str) -> str:
        p = Path(path)
        if not p.exists():
            raise ValueError(
                f"Path not found: {path}. Remedy: pass a .py file "
                "or directory visible to the server."
            )
        files = [p] if p.is_file() else sorted(p.rglob("*.py"))
        new = unchanged = changed = 0
        for f in files:
            result = lift_source(f.read_text(encoding="utf-8", errors="replace"), name=f.stem)
            defs_by_name = {d.name: d for d in result.module.defs}
            for entry in result.entries:
                node = defs_by_name.get(entry.name.split(".")[0])
                if node is None or entry.kind != "fn" or "." in entry.name:
                    continue  # records/methods: tracked via their record in v1
                full = self.store.put(node)
                key = (str(f), entry.name)
                prev = self._lift_index.get(key)
                if prev == full:
                    unchanged += 1
                    continue
                if prev is None:
                    self.sheet_log.append(
                        f"{self._disp(full)} {entry.name}{entry.sig} {entry.effects}"
                    )
                    new += 1
                else:
                    self.sheet_log.supersede(
                        self._disp(prev).lstrip("#"),
                        self._disp(full).lstrip("#"),
                        f"{entry.name}{entry.sig}",
                    )
                    changed += 1
                self._lift_index[key] = full
                self._lifted[entry.name] = full
        if new == 0 and changed == 0:
            return f"unchanged ({unchanged} definitions, hashes identical)"
        return f"lifted: {new} new, {changed} changed (old -> new appended), {unchanged} unchanged"

    def lifted_fns(self) -> dict[str, str]:
        return dict(self._lifted)

    # ---- sigil modules ---------------------------------------------------------
    def load_sigil_source(self, src: str, name: str = "<input>") -> dict:
        mod = parse_module(src)
        module_hash = self.store.put(mod)
        info: dict = {"module": module_hash, "goals": {}, "fns": {}, "invariants": {}}
        for d in mod.defs:
            if isinstance(d, Goal):
                gh = self.store.put(d)
                self.store.register_goal(gh, module_hash, d.name)
                info["goals"][d.name] = gh
                fx = printer.pfx(d.fx) if d.fx is not None else "pure"
                self.sheet_log.append(
                    f"{self._disp(gh)} goal {d.name} {fx} {self.store.status(gh)}"
                )
            elif isinstance(d, Invariant):
                ih = self.store.put(d)
                info["invariants"][d.name] = ih
                self.store.register_goal(ih, module_hash, d.name, extra={"kind": "invariant"})
                self.sheet_log.append(
                    f"{self._disp(ih)} invariant {d.name} over {', '.join(d.over)}"
                )
            elif isinstance(d, Fn):
                fh = self.store.put(d)
                info["fns"][d.name] = fh
                fx = printer.pfx(d.fx) if d.fx is not None else "pure?"
                self.sheet_log.append(
                    f"{self._disp(fh)} {d.name}({printer.pparams(d.params)}) {fx}"
                )
        return info

    # ---- sheet / expand ----------------------------------------------------------
    def sheet(self) -> str:
        return self.sheet_log.render()

    def expand(self, ref: str, form: str = "source") -> str:
        full = self.store.resolve(ref)
        node = self.store.get(full)
        self.sheet_log.log_expand(full)
        if form == "canonical":
            # N3 (firstuse): the patch-path schema, exactly as ops address it.
            import json

            return json.dumps(to_data(node), indent=2, sort_keys=True)
        if form != "source":
            raise ValueError(
                f"Unknown expand form {form!r}. Remedy: use 'source' (readable "
                "projection) or 'canonical' (the patchable data form)."
            )
        return self._project(node)

    def _project(self, node: Node) -> str:
        if isinstance(node, Fn):
            if isinstance(node.body, HostBlock):
                return ir_source(node.body.data)
            return printer.pfn(node)
        if isinstance(node, Goal):
            return printer.pgoal(node)
        if isinstance(node, Module):
            return printer.print_module(node)
        import json

        return json.dumps(to_data(node), indent=2, sort_keys=True)

    # ---- patch (R3: auto-verify) -----------------------------------------------------
    def patch(
        self, ref: str, ops: list[dict], inputs: dict | None = None, timeout: float = 10.0
    ) -> dict:
        full = self.store.resolve(ref)
        node = self.store.get(full)
        new_data = apply_ops(to_data(node), ops)
        new_node = from_data(new_data)
        new_full = self.store.put(new_node)
        sig = getattr(new_node, "name", "")
        # N6 (firstuse): display form returned alongside the full hash (below)
        self.sheet_log.supersede(
            self._disp(full).lstrip("#"), self._disp(new_full).lstrip("#"), sig
        )
        result: dict = {"new_hash": new_full, "display": self._disp(new_full)}
        if not isinstance(new_node, Fn):
            result["verify"] = "unverified: not an implementation fn"
            return result
        goal_entry = next(
            (
                (gh, e)
                for gh, e in self.store.goals().items()
                if e["name"] == new_node.name and e.get("kind") != "invariant"
            ),
            None,
        )
        if goal_entry is None:
            result["verify"] = "unverified: no goal bound"
            module = self._module_containing(new_node.name)
            if module is not None:
                defs = [
                    new_node if (isinstance(d, Fn) and d.name == new_node.name) else d
                    for d in module.defs
                ]
                new_module = Module(
                    name=module.name, imports=module.imports, defs=defs, fx=module.fx
                )
                result.update(self._reverify_invariants(new_module, new_node.name, inputs, timeout))
            return result
        goal_hash, entry = goal_entry
        goal = self.store.get(goal_hash)
        if goal.inputs and inputs is None:
            result["verify"] = (
                "unverified: inputs required — call "
                f"verify('{self._disp(goal_hash)}', inputs={{...}})"
            )
            return result
        module = self.store.get(entry["module"])
        defs = [
            new_node if (isinstance(d, Fn) and d.name == new_node.name) else d for d in module.defs
        ]
        new_module = Module(name=module.name, imports=module.imports, defs=defs)
        new_module_hash = self.store.put(new_module)
        self.store.register_goal(goal_hash, new_module_hash, goal.name)
        verdict = run_verify(self.store, new_module, goal.name, inputs, timeout=timeout)
        result["verify"] = verdict.to_dict()
        result.update(self._reverify_invariants(new_module, new_node.name, inputs, timeout))
        if verdict.status != "pass":
            # R3: structured feedback aimed at a patch of the failing subtree,
            # never "regenerate the function". Keep it small.
            result["target_subtree"] = new_full
            result["hint"] = (
                "patch the implementation subtree at this hash; do not regenerate the function"
            )
        return result

    def patch_snippet(
        self, ref: str, snippet: str, inputs: dict | None = None, timeout: float = 10.0
    ) -> dict:
        """Patch by replacement source (v1.1): Sigil tree-diffs the canonical
        forms and emits the minimal ops itself — no path authoring."""
        full = self.store.resolve(ref)
        node = self.store.get(full)
        if not isinstance(node, Fn):
            raise ValueError(
                f"{ref} is not a function. Remedy: snippet-patch targets fn definitions."
            )
        text = snippet.strip()
        if isinstance(node.body, HostBlock):
            from sigil.lift.python import lift_source

            new_fn = lift_source(text + "\n", name="snippet").module.defs[0]
        else:
            new_fn = parse_module("module _snippet\n\n" + text + "\n").defs[0]
        if getattr(new_fn, "name", None) != node.name:
            raise ValueError(
                f"Snippet defines {getattr(new_fn, 'name', '?')!r} but the target "
                f"is {node.name!r} — the name is part of identity. Remedy: keep "
                "the same name, or load_module a new definition instead."
            )
        ops = diff_data(to_data(node), to_data(new_fn))
        if not ops:
            return {
                "new_hash": full,
                "display": self._disp(full),
                "verify": "unchanged: snippet is canonically identical",
            }
        return self.patch(full, ops, inputs=inputs, timeout=timeout)

    def _module_containing(self, fn_name: str):
        for _gh, e in self.store.goals().items():
            if e.get("module"):
                try:
                    m = self.store.get(e["module"])
                except ValueError:
                    continue
                if isinstance(m, Module) and any(
                    isinstance(d, Fn) and d.name == fn_name for d in m.defs
                ):
                    return m
        return None

    def _reverify_invariants(
        self, module: Module, fn_name: str, inputs: dict | None, timeout: float
    ) -> dict:
        """R3, extended to invariants: patching a fn re-verifies every
        invariant that ranges over it."""
        from sigil.verify.runner import run_verify_invariant

        results = []
        for d in module.defs:
            if isinstance(d, Invariant) and fn_name in d.over:
                try:
                    verdict = run_verify_invariant(
                        self.store, module, d.name, inputs, timeout=timeout
                    )
                except ValueError as exc:
                    results.append({"name": d.name, "status": "error", "detail": str(exc)})
                    continue
                results.append(verdict)
                # Bug 1 (V2_REPORT): on pass, re-register the invariant against
                # the PATCHED module — otherwise a later verify_invariant runs
                # against stale pre-patch state and contradicts this verdict.
                if verdict.get("status") == "pass":
                    inv_hash = next(
                        (
                            gh
                            for gh, e in self.store.goals().items()
                            if e["name"] == d.name and e.get("kind") == "invariant"
                        ),
                        None,
                    )
                    if inv_hash is not None:
                        new_mod_hash = self.store.put(module)
                        self.store.register_goal(
                            inv_hash, new_mod_hash, d.name, extra={"kind": "invariant"}
                        )
                        self.store.bind(inv_hash, verdict.get("invariant_hash", inv_hash))
        return {"invariants": results} if results else {}

    def verify_invariant(self, ref: str, inputs: dict | None = None, timeout: float = 10.0) -> dict:
        from sigil.verify.runner import run_verify_invariant

        inv_hash = self.store.resolve(ref)
        inv = self.store.get(inv_hash)
        if not isinstance(inv, Invariant):
            raise ValueError(f"{ref} is not an invariant. Remedy: pass an invariant hash.")
        entry = self.store.goals().get(inv_hash)
        if entry is None or entry.get("module") is None:
            raise ValueError(
                f"Invariant {ref} has no registered module. Remedy: load the module first."
            )
        module = self.store.get(entry["module"])
        return run_verify_invariant(self.store, module, inv.name, inputs, timeout=timeout)

    def propose_contract(
        self,
        fn_ref: str,
        clauses: list[str],
        inputs: dict | None = None,
        intent: str = "proposed by agent (Tier 3)",
    ) -> dict:
        """Tier 3 (v2.0): an agent PROPOSES verify clauses for a lifted fn.
        The proposal registers provisional and is validated immediately when
        inputs allow — it can only bind by passing verification. A proposer
        that skipped this step would launder guesses into specs."""
        from sigil.core.ast import Param as _Param
        from sigil.core.ast import VerifyClause as _VC
        from sigil.core.ir import ir_source
        from sigil.lang.parser import Parser, tokenize
        from sigil.verify.runner import run_verify_py

        full = self.store.resolve(fn_ref)
        fn = self.store.get(full)
        if not isinstance(fn, Fn):
            raise ValueError(
                f"{fn_ref} is not a function. Remedy: propose against "
                "a lifted fn hash from the sheet."
            )
        parsed = []
        for text in clauses:
            p = Parser(tokenize(text))
            parsed.append(_VC(expr=p.expr()))
        goal = Goal(
            name=fn.name,
            intent=intent,
            inputs=[_Param(name=p.name) for p in fn.params],
            verify=parsed,
        )
        goal_hash = self.store.put(goal)
        self.store.register_goal(goal_hash, None, fn.name, extra={"tier": 3, "impl": full})
        self.sheet_log.append(f"{self._disp(goal_hash)} goal {fn.name} proposed (tier 3)")
        result: dict = {"goal_hash": goal_hash, "display": self._disp(goal_hash)}
        if inputs is None and goal.inputs:
            result["verify"] = "provisional: inputs required to validate"
            return result
        if not isinstance(fn.body, HostBlock) or fn.body.lang not in ("python",):
            result["verify"] = "provisional: validation supports python-lifted fns in v2.0"
            return result
        py_src = ir_source(fn.body.data)
        verdict = run_verify_py(self.store, py_src, fn.name, goal, inputs)
        result["verify"] = verdict.to_dict()
        outcome = "verified" if verdict.status == "pass" else "rejected (stays provisional)"
        self.sheet_log.append(f"{self._disp(goal_hash)} goal {fn.name} tier-3 {outcome}")
        return result

    # ---- verify ------------------------------------------------------------------------
    def verify(self, ref: str, inputs: dict | None = None, timeout: float = 10.0) -> dict:
        goal_hash = self.store.resolve(ref)
        goal = self.store.get(goal_hash)
        if not isinstance(goal, Goal):
            raise ValueError(f"{ref} is not a goal. Remedy: pass a goal hash from the sheet.")
        entry = self.store.goals().get(goal_hash)
        if entry is None or entry.get("module") is None:
            raise ValueError(
                f"Goal {ref} has no registered module. "
                "Remedy: load the module first (lift or load_sigil_source)."
            )
        module = self.store.get(entry["module"])
        verdict = run_verify(self.store, module, goal.name, inputs, timeout=timeout)
        return {
            **verdict.to_dict(),
            "cached": verdict.cached,
            "goal_status": self.store.status(goal_hash),
        }

    # ---- session ---------------------------------------------------------------------------
    def session_stats(self) -> dict:
        return self.sheet_log.stats()

    def session_close(self) -> dict:
        return {
            "stats": self.sheet_log.stats(),
            "compacted_sheet_for_next_session": self.sheet_log.compacted(),
        }
