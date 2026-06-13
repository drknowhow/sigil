"""sigil watch — the seatbelt is always on (v1.2, P1.3).

Stdlib polling engine (no dependencies): file save -> re-build/re-lift ->
re-verify every bound goal touching that file. WatchState.poll() is the
testable core; the CLI wraps it in a sleep loop.
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path

from sigil.store.repo import Store


class WatchState:
    def __init__(self, paths: list[str], store_dir: str | Path) -> None:
        self.paths = [Path(p) for p in paths]
        self.store = Store.create(Path(store_dir))
        self._mtimes = self._scan()

    def _files(self):
        for root in self.paths:
            if root.is_file():
                yield root
            else:
                yield from root.rglob("*.sg")
                yield from (p for p in root.rglob("*.py") if "__pycache__" not in p.parts)

    def _scan(self) -> dict[str, str]:
        # content digests, not mtimes: editor saves within the same second and
        # coarse filesystem timestamps must not hide changes
        out: dict[str, str] = {}
        for f in self._files():
            try:
                out[str(f)] = hashlib.sha256(f.read_bytes()).hexdigest()
            except OSError:
                continue
        return out

    def poll(self) -> list[str]:
        """One pass: detect changes, re-verify, return human-readable events."""
        now = self._scan()
        changed = [p for p, m in now.items() if self._mtimes.get(p) != m] + [
            p for p in self._mtimes if p not in now
        ]
        self._mtimes = now
        events: list[str] = []
        for path in sorted(set(changed)):
            p = Path(path)
            if not p.exists():
                events.append(f"{p.name}: removed")
                continue
            if p.suffix == ".sg":
                events += self._handle_sg(p)
            else:
                events += self._handle_py(p)
        return events

    def _handle_sg(self, p: Path) -> list[str]:
        from sigil.core.ast import Goal
        from sigil.lang.parser import parse_module
        from sigil.transpile.build import BuildError, build_source
        from sigil.verify.runner import run_verify

        events = []
        try:
            build_source(p.read_text(encoding="utf-8"), name=str(p))
            mod = parse_module(p.read_text(encoding="utf-8"))
        except (BuildError, ValueError) as exc:
            return [f"{p.name}: build rejected — {exc}"]
        self.store.put(mod)
        for d in mod.defs:
            if not isinstance(d, Goal):
                continue
            gh = self.store.put(d)
            entry = {"name": d.name}
            if d.inputs_ref:
                entry["inputs_file"] = str(p.parent / d.inputs_ref)
            self.store.register_goal(gh, module_hash=self.store.put(mod), name=d.name, extra=entry)
            try:
                inputs = self.store.recorded_inputs(gh)
            except ValueError as exc:
                events.append(f"{p.name}: goal {d.name} — {exc}")
                continue
            if inputs is None and d.inputs:
                events.append(f"{p.name}: goal {d.name} skipped (no recorded inputs)")
                continue
            v = run_verify(self.store, mod, d.name, inputs)
            events.append(f"{p.name}: goal {d.name} verify {v.status}")
        return events

    def _handle_py(self, p: Path) -> list[str]:
        from sigil.lift.python import check_module_budget

        try:
            violations = check_module_budget(p.read_text(encoding="utf-8"), name=p.name)
        except (ValueError, SyntaxError) as exc:
            return [f"{p.name}: {exc}"]
        if violations:
            return [f"{p.name}: {v}" for v in violations]
        return [f"{p.name}: lint ok (module budget respected)"]


def watch_loop(paths: list[str], store_dir: str, interval: float = 2.0) -> None:
    state = WatchState(paths, store_dir)
    print(f"sigil watch: {len(state._mtimes)} files; every {interval}s (Ctrl+C stops)")
    while True:
        for event in state.poll():
            print(time.strftime("%H:%M:%S"), event, flush=True)
        time.sleep(interval)
