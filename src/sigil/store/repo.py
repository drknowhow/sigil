""".sigil/ object store (plan Phase 3).

Layout (all paths relative — the store is relocatable, plan section 10):
  .sigil/objects/<full-hash>.cbor   canonical CBOR of the node's data
  .sigil/index.json                 goals registry + goal<->impl bindings
  .sigil/config.json                {"short_len": 4|8} (collision escalation, sticky)
  .sigil/vcache/<goal>-<impl>.json  immutable verify verdicts

Identity rules per the sigil-canonical-hashing skill: full sha256 persisted;
short form display-only; 4 -> 8 char escalation on prefix collision is a
store-level, sticky setting. Bindings live here, never inside objects.
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
        self._index_path = self.dir / "index.json"
        self._config_path = self.dir / "config.json"

    # ---- lifecycle ---------------------------------------------------------
    @classmethod
    def create(cls, root: Path) -> Store:
        store = cls(root)
        store.objects.mkdir(parents=True, exist_ok=True)
        store.vcache.mkdir(parents=True, exist_ok=True)
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
    def register_goal(self, goal_hash: str, module_hash: str | None, name: str) -> None:
        index = self._read_index()
        index["goals"][goal_hash] = {"name": name, "module": module_hash}
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

    def status(self, goal_hash: str) -> str:
        return "verified" if self.binding(goal_hash) else "provisional"

    def describe_goal(self, goal_hash: str) -> str:
        """Sheet-line description; 'provisional' must stay visible (skill rule)."""
        name = self._read_index()["goals"].get(goal_hash, {}).get("name", "?")
        b = self.binding(goal_hash)
        if b is None:
            return f"{self.display(goal_hash)} goal {name} provisional"
        return f"{self.display(goal_hash)} goal {name} verified -> {self.display(b['impl'])}"

    # ---- verify verdict cache --------------------------------------------------
    def cache_get(self, goal_hash: str, impl_hash: str) -> dict | None:
        p = self.vcache / f"{goal_hash}-{impl_hash}.json"
        return json.loads(p.read_text()) if p.exists() else None

    def cache_put(self, goal_hash: str, impl_hash: str, verdict: dict) -> None:
        (self.vcache / f"{goal_hash}-{impl_hash}.json").write_text(
            json.dumps(verdict, sort_keys=True)
        )
