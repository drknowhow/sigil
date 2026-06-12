"""R1 — append-only session context (sigil-harness-rules skill).

The session sheet is an ordered log. Permitted op: append. Forbidden:
reorder, rewrite, delete. Superseding appends '#old -> #new sig'; the old
line stays. GC happens only at session boundaries (session_close emits a
compacted sheet for the NEXT session). Cached-prefix economics depend on
this: a byte-stable longer prefix beats a rewritten shorter one.
"""

from __future__ import annotations


def est_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class SessionSheet:
    def __init__(self) -> None:
        self._lines: list[str] = []
        self._expansions: list[str] = []
        self._superseded: set[str] = set()

    def append(self, line: str) -> None:
        self._lines.append(line)

    def supersede(self, old: str, new: str, sig: str = "") -> None:
        self._superseded.add(old)
        self.append(f"#{old} -> #{new} {sig}".rstrip())

    def log_expand(self, ref: str) -> None:
        self._expansions.append(ref)

    def render(self) -> str:
        return "\n".join(self._lines)

    def stats(self) -> dict:
        return {
            "lines": len(self._lines),
            "expansions": len(self._expansions),
            "superseded": len(self._superseded),
            "est_tokens": est_tokens(self.render()),
        }

    def compacted(self) -> str:
        """For the NEXT session only (R1 forbids compaction mid-session)."""
        keep = [
            ln
            for ln in self._lines
            if " -> " in ln or not any("#" + old in ln for old in self._superseded)
        ]
        return "\n".join(keep)
