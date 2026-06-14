""".sigil/ object store (plan Phase 3).

Layout (all paths relative — the store is relocatable, plan section 10):
  .sigil/objects/<full-hash>.cbor   canonical CBOR of the node's data
  .sigil/src/<full-hash>.txt        author's original source (Muninn Part 1)
  .sigil/index.json                 goals registry + goal<->impl bindings
  .sigil/config.json                {"short_len": 4|8} (collision escalation, sticky)
  .sigil/vcache/<goal>-<impl>.json  immutable verify verdicts

Identity rules per the sigil-canonical-hashing skill: full sha256 persisted;
short form display-only; 4 -> 8 char escalation on prefix collision is a
store-level, sticky setting. Bindings live here, never inside objects. The
source sidecar follows the same rule: keyed by the node's hash, never hashed.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import cbor2

from sigil.core.ast import Node, from_data, to_data
from sigil.core.hash import canonical_cbor, digest_node


class Store:
    DIRNAME = ".sigil"

    def __init__(self, root: Path) -> None:
        self.dir = Path(root) / self.DIRNAME
        self.objects = self.dir / "objects"
        self.vcache = self.dir / "vcache"
        self.src = self.dir / "src"
        self._index_path = self.dir / "index.json"
        self._config_path = self.dir / "config.json"

    # ---- lifecycle ---------------------------------------------------------
    @classmethod
    def create(cls, root: Path) -> Store:
        store = cls(root)
        store.objects.mkdir(parents=True, exist_ok=True)
        store.vcache.mkdir(parents=True, exist_ok=True)
        store.src.mkdir(parents=True, exist_ok=True)
        if not store._index_path.exists():
            store._write_index({"goals": {}, "bindings": {}})
        if not store._config_path.exists():
            store._config_path.write_text(json.dumps({"short_len": 4}))
        return store

    @classmethod
    def open(cls, root: Path) -> Store:
        store = cls(root)
        if not store.dir.is_dir():
            raise ValueError(
                f"No {cls.DIRNAME}/ store found under {root}. "
                "Remedy: run 'sigil build <module.sg> --store <dir>' first, "
                "or point --store at the directory containing .sigil/."
            )
        return store

    def _read_index(self) -> dict:
        return json.loads(self._index_path.read_text())

    def _write_index(self, index: dict) -> None:
        self._index_path.write_text(json.dumps(index, indent=2, sort_keys=True))

    # ---- objects -----------------------------------------------------------
    def put(self, node: Node) -> str:
        full = digest_node(node)
        path = self.objects / f"{full}.cbor"
        if not path.exists():
            path.write_bytes(canonical_cbor(to_data(node)))
            self._check_collision(full)
        return full

    def get(self, ref: str) -> Node:
        full = self.resolve(ref)
        return from_data(cbor2.loads((self.objects / f"{full}.cbor").read_bytes()))

    def resolve(self, ref: str) -> str:
        prefix = ref.lstrip("#")
        path = self.objects / f"{prefix}.cbor"
        if len(prefix) == 64 and path.exists():
            return prefix
        matches = [p.stem for p in self.objects.glob(f"{prefix}*.cbor")]
        if not matches:
            raise ValueError(
                f"Object {ref!r} not found in the store. "
                "Remedy: check the hash (see 'sigil build --json' output or the sheet), "
                "or re-run build --store to register it."
            )
        if len(matches) > 1:
            raise ValueError(
                f"Hash prefix {ref!r} is ambiguous ({len(matches)} matches). "
                "Remedy: use more hash characters."
            )
        return matches[0]

    # ---- original source sidecar (Muninn Part 1, D-043) --------------------
    def put_source(self, full: str, text: str) -> None:
        """Keep the author's original source for a node, keyed by the same
        full hash. First write wins: two texts that canonicalize to one hash
        share one record (content addressing). This is store-side data, never
        hashed and never inside the object -- the same rule bindings follow
        (sigil-canonical-hashing skill), so identity and the digest are
        untouched."""
        self.src.mkdir(parents=True, exist_ok=True)
        path = self.src / f"{full}.txt"
        if not path.exists():
            path.write_text(text, encoding="utf-8")

    def source(self, full: str) -> str | None:
        """The author's original source for a node, or None when the node was
        never lifted from text (e.g. it exists only as a patched AST)."""
        path = self.src / f"{full}.txt"
        return path.read_text(encoding="utf-8") if path.exists() else None

    # ---- short display with sticky escalation -------------------------------
    @property
    def short_len(self) -> int:
        return json.loads(self._config_path.read_text())["short_len"]

    def _check_collision(self, new_full: str) -> None:
        if self.short_len >= 8:
            return
        prefix = new_full[:4]
        twins = [p.stem for p in self.objects.glob(f"{prefix}*.cbor")]
        if len(twins) > 1:
            self._config_path.write_text(json.dumps({"short_len": 8}))

    def display(self, full: str) -> str:
        return "#" + full[: self.short_len]

    # ---- goals + bindings ----------------------------------------------------
    def register_goal(
        self, goal_hash: str, module_hash: str | None, name: str, extra: dict | None = None
    ) -> None:
        index = self._read_index()
        entry = {"name": name, "module": module_hash}
        if extra:
            entry.update(extra)
        index["goals"][goal_hash] = entry
        self._write_index(index)

    def goals(self) -> dict:
        return self._read_index()["goals"]

    def bind(self, goal_hash: str, impl_hash: str) -> None:
        """Bind goal<->impl. Only the verify runner calls this, only on pass."""
        index = self._read_index()
        index["bindings"][goal_hash] = {
            "impl": impl_hash,
            "verified_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        self._write_index(index)

    def binding(self, goal_hash: str) -> dict | None:
        return self._read_index()["bindings"].get(goal_hash)

    def unbind(self, goal_hash: str, reason: str) -> None:
        """Retire a contract deliberately: tombstone with date + reason (v1.1).
        The ledger stays honest — retirement is ceremony, not deletion."""
        import time as _t

        index = self._read_index()
        prior = index["bindings"].pop(goal_hash, None)
        index.setdefault("tombstones", {})[goal_hash] = {
            "reason": reason,
            "retired_at": _t.strftime("%Y-%m-%dT%H:%M:%SZ", _t.gmtime()),
            "prior_binding": prior,
        }
        self._write_index(index)

    def tombstone(self, goal_hash: str) -> dict | None:
        return self._read_index().get("tombstones", {}).get(goal_hash)

    def status(self, goal_hash: str) -> str:
        if self.tombstone(goal_hash) is not None:
            return "retired"
        return "verified" if self.binding(goal_hash) else "provisional"

    def describe_goal(self, goal_hash: str) -> str:
        """Sheet-line description; 'provisional' must stay visible (skill rule)."""
        name = self._read_index()["goals"].get(goal_hash, {}).get("name", "?")
        ts = self.tombstone(goal_hash)
        if ts is not None:
            return (
                f"{self.display(goal_hash)} goal {name} retired "
                f"({ts['retired_at'][:10]}: {ts['reason']})"
            )
        b = self.binding(goal_hash)
        if b is None:
            return f"{self.display(goal_hash)} goal {name} provisional"
        return f"{self.display(goal_hash)} goal {name} verified -> {self.display(b['impl'])}"

    # ---- recorded inputs (v1.2, D-020 revisited deliberately) -------------------
    def record_inputs(self, goal_hash: str, inputs: dict) -> None:
        index = self._read_index()
        index["goals"].setdefault(goal_hash, {"name": "?", "module": None})
        index["goals"][goal_hash]["inputs"] = inputs
        self._write_index(index)

    def recorded_inputs(self, goal_hash: str) -> dict | None:
        """Inline registry inputs, else the goal's inputs_ref file (resolved
        against the store root), else the inputs_file registry path."""
        entry = self._read_index()["goals"].get(goal_hash, {})
        if "inputs" in entry:
            return entry["inputs"]
        ref = entry.get("inputs_file")
        if ref is None:
            try:
                node = self.get(goal_hash)
                ref = getattr(node, "inputs_ref", None)
            except ValueError:
                ref = None
        if ref is None:
            return None
        p = Path(ref)
        if not p.is_absolute():
            p = self.dir.parent / p
        if not p.exists():
            raise ValueError(
                f"Recorded-inputs file {ref!r} for goal {self.display(goal_hash)} "
                f"not found at {p}. Remedy: create it (a JSON object keyed by the "
                "goal's input names) or pass inputs explicitly."
            )
        return json.loads(p.read_text())

    def append_counterexample(self, goal_hash: str, case: dict) -> None:
        index = self._read_index()
        entry = index["goals"].setdefault(goal_hash, {"name": "?", "module": None})
        entry.setdefault("counterexamples", []).append(case)
        if "inputs" not in entry and "inputs_file" not in entry:
            entry["inputs"] = case  # the counterexample becomes the recorded input
        self._write_index(index)

    # ---- verify verdict cache (keyed goal+impl+inputs, v1.2) --------------------
    def cache_get(self, goal_hash: str, impl_hash: str, inputs_hash: str = "-") -> dict | None:
        p = self.vcache / f"{goal_hash}-{impl_hash}-{inputs_hash}.json"
        return json.loads(p.read_text()) if p.exists() else None

    def cache_put(
        self, goal_hash: str, impl_hash: str, verdict: dict, inputs_hash: str = "-"
    ) -> None:
        (self.vcache / f"{goal_hash}-{impl_hash}-{inputs_hash}.json").write_text(
            json.dumps(verdict, sort_keys=True)
        )
