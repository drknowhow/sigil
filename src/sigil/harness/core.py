"""Harness state: the digest/expand/patch/verify loop over a .sigil store.

Transport-independent (server.py wires this to FastMCP). Behavior rules come
from the sigil-harness-rules skill: R1 append-only sheet (context.py), R2
expand-over-regenerate, R3 verify-before-display with small structured
failure feedback.
"""

from __future__ import annotations

from pathlib import Path

from sigil.core.ast import Fn, Goal, HostBlock, Module, Node, from_data, to_data
from sigil.core.patch import apply_ops, diff_data
from sigil.core.pycanon import host_source
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
        info: dict = {"module": module_hash, "goals": {}, "fns": {}}
        for d in mod.defs:
            if isinstance(d, Goal):
                gh = self.store.put(d)
                self.store.register_goal(gh, module_hash, d.name)
                info["goals"][d.name] = gh
                fx = printer.pfx(d.fx) if d.fx is not None else "pure"
                self.sheet_log.append(
                    f"{self._disp(gh)} goal {d.name} {fx} {self.store.status(gh)}"
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
                return host_source(node.body.data)
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
            ((gh, e) for gh, e in self.store.goals().items() if e["name"] == new_node.name), None
        )
        if goal_entry is None:
            result["verify"] = "unverified: no goal bound"
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
