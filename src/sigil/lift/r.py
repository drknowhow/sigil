"""R frontend (v2.0, S2) — the scientific-reproducibility wedge.

Tier 1: tokenizer-based canonical form (comments/whitespace never reach the
hash) for top-level `name <- function(...)` definitions, lowered to a small
IR: ["def", name, ["rargs", [params]], ["rtok", [tokens]], [], 0] — same
shape family as Python's, so sheets/patches/store work unchanged.

Tier 2-lite: token-rule effects. Per PROPOSALS_RESPONSE.md, R effect
inference is explicitly HARD (NSE, promises, library() side effects) —
unknown library() loads and system-ish calls earn !unsafe? early and often.
Result-hash reproducibility checks live in `sigil check-r` (needs Rscript).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from sigil.core.ast import Effect, EffectRow, Fn, HostBlock, Module, Param
from sigil.core.hash import digest_data
from sigil.lift.python import SheetEntry

_TOKEN = re.compile(
    r"#[^\n]*"  # comment (dropped)
    r"|'(?:\\.|[^'\\])*'"  # strings
    r'|"(?:\\.|[^"\\])*"'
    r"|`[^`]+`"  # backtick names
    r"|%[^%\s]*%"  # %in%, %>%, custom operators
    r"|<<-|<-|->>|->|==|!=|<=|>=|&&|\|\||\.\.\."
    r"|[0-9]+\.?[0-9]*(?:[eE][+-]?[0-9]+)?L?"
    r"|[A-Za-z._][A-Za-z0-9._]*"
    r"|\S"
)

R_EFFECT_RULES: dict[str, tuple[str, str | None, bool]] = {
    # token -> (effect, mode, uncertain)
    "read.csv": ("fs", "read", False),
    "read.table": ("fs", "read", False),
    "readRDS": ("fs", "read", False),
    "readLines": ("fs", "read", False),
    "scan": ("fs", "read", False),
    "load": ("fs", "read", False),
    "file.exists": ("fs", "read", False),
    "list.files": ("fs", "read", False),
    "write.csv": ("fs", "write", False),
    "write.table": ("fs", "write", False),
    "saveRDS": ("fs", "write", False),
    "save": ("fs", "write", False),
    "sink": ("fs", "write", False),
    "pdf": ("fs", "write", False),
    "png": ("fs", "write", False),
    "file.remove": ("fs", "write", False),
    "download.file": ("net", None, False),
    "url": ("net", None, False),
    "curl": ("net", None, False),
    "GET": ("net", None, False),
    "Sys.getenv": ("env", None, False),
    "Sys.setenv": ("env", None, False),
    "Sys.time": ("clock", None, False),
    "Sys.Date": ("clock", None, False),
    "date": ("clock", None, False),
    "proc.time": ("clock", None, False),
    "set.seed": ("rand", None, False),
    "runif": ("rand", None, False),
    "rnorm": ("rand", None, False),
    "sample": ("rand", None, False),
    "rbinom": ("rand", None, False),
    "rpois": ("rand", None, False),
    "system": ("unsafe", None, False),
    "system2": ("unsafe", None, False),
    "shell": ("unsafe", None, False),
    "eval": ("unsafe", True, False),
    "library": ("unsafe", None, True),
    "require": ("unsafe", None, True),
    "source": ("unsafe", None, True),
    "do.call": ("unsafe", None, True),
    "print": ("io", None, False),
    "cat": ("io", None, False),
    "message": ("io", None, False),
    "dbConnect": ("db", None, False),
    "dbGetQuery": ("db", None, False),
    "dbWriteTable": ("db", None, False),
}


def tokenize_r(source: str) -> list[str]:
    return [t for t in _TOKEN.findall(source) if not t.startswith("#")]


@dataclass(frozen=True)
class RLift:
    module: Module
    entries: list[SheetEntry] = field(default_factory=list)
    stats: dict = field(default_factory=dict)


def _fn_spans(tokens: list[str]):
    """Yield (name, params, body_tokens) for top-level name <- function(...)."""
    i = 0
    while i < len(tokens) - 3:
        if tokens[i + 1] in ("<-", "=") and tokens[i + 2] == "function" and tokens[i + 3] == "(":
            name = tokens[i].strip("`")
            j = i + 4
            depth = 1
            params: list[str] = []
            while j < len(tokens) and depth:
                t = tokens[j]
                depth += t == "("
                depth -= t == ")"
                if depth == 1 and re.match(r"[A-Za-z._]", t) and tokens[j - 1] in ("(", ","):
                    params.append(t)
                j += 1
            body_start = j
            if j < len(tokens) and tokens[j] == "{":
                depth = 1
                j += 1
                while j < len(tokens) and depth:
                    depth += tokens[j] == "{"
                    depth -= tokens[j] == "}"
                    j += 1
            else:  # single-expression body: consume to end of line-ish (next top fn)
                while j < len(tokens) and not (
                    j + 3 < len(tokens)
                    and tokens[j + 1] in ("<-", "=")
                    and tokens[j + 2] == "function"
                ):
                    j += 1
            yield name, params, tokens[body_start:j]
            i = j
        else:
            i += 1


def _effects_for(tokens: list[str]) -> EffectRow:
    found: dict[tuple, bool] = {}
    for t in tokens:
        rule = R_EFFECT_RULES.get(t)
        if rule:
            name, mode, unc = rule
            key = (name, mode)
            found[key] = found.get(key, True) and unc
    effects = [
        Effect(name=n, scope=None, uncertain=u, mode=m)
        for (n, m), u in sorted(found.items(), key=lambda kv: (kv[0][0], kv[0][1] or ""))
    ]
    return EffectRow(effects=effects, uncertain=True)


def lift_r_source(source: str, name: str = "<r>") -> RLift:
    tokens = tokenize_r(source)
    defs: list = []
    entries: list[SheetEntry] = []
    for fn_name, params, body in _fn_spans(tokens):
        fx = _effects_for(body)
        ir = ["def", fn_name, ["rargs", params], ["rtok", body], [], 0]
        fn = Fn(
            name=fn_name,
            params=[Param(name=p) for p in params],
            fx=fx,
            body=HostBlock(lang="r", data=ir),
        )
        defs.append(fn)
        from sigil.lift.effects import render_row

        entries.append(
            SheetEntry(
                digest=digest_data(ir),
                name=fn_name,
                sig="(" + ", ".join(params) + ")",
                effects=render_row(fx),
                kind="fn",
            )
        )
    module = Module(name=name, defs=defs)
    stats = {
        "functions": len(entries),
        "language": "r",
        "source_tokens_est": max(1, len(source) // 4),
    }
    return RLift(module=module, entries=entries, stats=stats)
