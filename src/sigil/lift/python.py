"""Tier 1 lifter: Python source -> Sigil Module + digest sheet.

Evolved from seed/sigil_lift.py (PoC). Differences, per the
sigil-canonical-hashing skill: digests are sha256 over canonical CBOR of the
canonical host AST (not ast.dump text); effects come from lift.effects
(origin + call-graph propagation, fixing the PoC's Path/!fs miss).
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field

from sigil.core.ast import EffectRow, Field, Fn, HostBlock, Import, Module, Param, Record, TypeExpr
from sigil.core.hash import DigestNamer, digest_data
from sigil.core.ir import lower_stmt
from sigil.lift.effects import infer_module_effects, render_row


@dataclass(frozen=True)
class SheetEntry:
    digest: str  # full sha256 hex (short form is display-only)
    name: str  # 'fn' or 'Cls.method' or 'Cls' for records
    sig: str
    effects: str  # display row, e.g. '!fs !net' or 'pure?'
    kind: str  # 'fn' | 'record'
    source: str | None = None  # original text (comments/docstring), Muninn Part 1


@dataclass(frozen=True)
class LiftResult:
    module: Module
    entries: list[SheetEntry] = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    module_fx: EffectRow | None = None  # from __sigil_fx__ = "!fs.read ..." (v1.1)


def _type_expr(node: ast.expr | None) -> TypeExpr | None:
    return TypeExpr(name=ast.unparse(node)) if node is not None else None


def _signature(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    parts = []
    for a in [*fn.args.posonlyargs, *fn.args.args, *fn.args.kwonlyargs]:
        parts.append(a.arg + (f" {ast.unparse(a.annotation)}" if a.annotation else ""))
    if fn.args.vararg:
        parts.append("*" + fn.args.vararg.arg)
    if fn.args.kwarg:
        parts.append("**" + fn.args.kwarg.arg)
    ret = f" -> {ast.unparse(fn.returns)}" if fn.returns else " -> ?"
    return f"({', '.join(parts)}){ret}"


def _lift_fn(node: ast.FunctionDef | ast.AsyncFunctionDef, fx: EffectRow) -> Fn:
    params = [
        Param(name=a.arg, ty=_type_expr(a.annotation))
        for a in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
    ]
    return Fn(
        name=node.name,
        params=params,
        ret=_type_expr(node.returns),
        fx=fx,
        body=HostBlock(lang="python", data=lower_stmt(node)),
    )


def _record_fields(cls: ast.ClassDef) -> list[Field]:
    out = []
    for s in cls.body:
        if isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name):
            out.append(Field(name=s.target.id, ty=_type_expr(s.annotation)))
        elif isinstance(s, ast.Assign):
            for t in s.targets:
                if isinstance(t, ast.Name):
                    out.append(Field(name=t.id, ty=None))
    return out


def est_tokens(text: str) -> int:
    """Rough chars/4 heuristic — display-only estimate; measured numbers
    (real tokenizer) are an examples/ deliverable, plan section 9."""
    return max(1, len(text) // 4)


def _orig_source(lines: list[str], node: ast.stmt) -> str | None:
    """The author's original text for a top-level def: comments, docstring and
    formatting included (Muninn Part 1). ast.get_source_segment omits leading
    decorators and the comment block above the def, so reconstruct the span:
    from the first decorator (or the def line), extended up over a contiguous
    run of comment-only lines, through end_lineno. Returns None if positions
    are unavailable (older AST / synthetic node) — the caller then falls back
    to the canonical projection."""
    start = getattr(node, "lineno", None)
    end = getattr(node, "end_lineno", None)
    if start is None or end is None:
        return None
    for d in getattr(node, "decorator_list", []) or []:
        if getattr(d, "lineno", start) < start:
            start = d.lineno
    # absorb the comment block directly above (no blank-line gap)
    while start > 1 and lines[start - 2].lstrip().startswith("#"):
        start -= 1
    return "\n".join(lines[start - 1 : end])


def lift_source(source: str, name: str = "<module>") -> LiftResult:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise ValueError(
            f"Cannot lift {name}: Python syntax error at line {exc.lineno}: {exc.msg}. "
            "Remedy: fix the syntax error (or exclude the file) and re-run 'sigil lift'."
        ) from exc

    rows = infer_module_effects(tree)
    module_fx = _module_fx(tree, name)
    lines = source.splitlines()
    pure_unknown = EffectRow(effects=[], uncertain=True)
    imports: list[Import] = []
    defs: list = []
    entries: list[SheetEntry] = []

    for s in tree.body:
        if isinstance(s, ast.Import):
            imports.extend(Import(module=a.name, names=[]) for a in s.names)
        elif isinstance(s, ast.ImportFrom):
            mod = ("." * s.level) + (s.module or "")
            imports.append(Import(module=mod, names=[a.name for a in s.names]))
        elif isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if s.name.startswith("__sigil_"):
                continue  # transpiler scaffolding, not user code (firstuse N5);
                # the effect analyzer still sees it via the call graph
            fx = rows.get(s.name, pure_unknown)
            fn = _lift_fn(s, fx)
            defs.append(fn)
            entries.append(
                SheetEntry(
                    digest=digest_data(lower_stmt(s)),
                    name=s.name,
                    sig=_signature(s),
                    effects=render_row(fx),
                    kind="fn",
                    source=_orig_source(lines, s),
                )
            )
        elif isinstance(s, ast.ClassDef):
            methods = []
            for m in s.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    key = f"{s.name}.{m.name}"
                    methods.append(_lift_fn(m, rows.get(key, pure_unknown)))
            rec = Record(name=s.name, fields=_record_fields(s), methods=methods)
            defs.append(rec)
            entries.append(
                SheetEntry(
                    digest=digest_data(lower_stmt(s)),
                    name=s.name,
                    sig="{" + ", ".join(f.name for f in rec.fields) + "}",
                    effects="rec",
                    kind="record",
                )
            )
            for m, mn in zip(
                methods,
                [x for x in s.body if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef))],
                strict=True,
            ):
                entries.append(
                    SheetEntry(
                        digest=digest_data(lower_stmt(mn)),
                        name=f"{s.name}.{m.name}",
                        sig=_signature(mn),
                        effects=render_row(m.fx),
                        kind="fn",
                    )
                )

    module = Module(name=name, imports=imports, defs=defs, fx=module_fx)
    stats = {
        "functions": sum(1 for e in entries if e.kind == "fn"),
        "records": sum(1 for e in entries if e.kind == "record"),
        "source_tokens_est": est_tokens(source),
    }
    return LiftResult(module=module, entries=entries, stats=stats, module_fx=module_fx)


def _module_fx(tree: ast.Module, name: str) -> EffectRow | None:
    """Read a module-level __sigil_fx__ = "..." budget declaration (v1.1)."""
    for s in tree.body:
        if (
            isinstance(s, ast.Assign)
            and len(s.targets) == 1
            and isinstance(s.targets[0], ast.Name)
            and s.targets[0].id == "__sigil_fx__"
            and isinstance(s.value, ast.Constant)
            and isinstance(s.value.value, str)
        ):
            from sigil.lang.parser import parse_fxrow

            try:
                return parse_fxrow(s.value.value)
            except ValueError as exc:
                raise ValueError(
                    f"Cannot parse __sigil_fx__ in {name}: {exc}. "
                    'Remedy: use effect-row syntax, e.g. "!fs.read(./cache) !net".'
                ) from exc
    return None


def check_module_budget(source: str, name: str = "<module>") -> list[str]:
    """Violation messages for a Python module's __sigil_fx__ budget (v1.1).
    Empty list = within budget (or no budget declared)."""
    from sigil.lift.effects import analyze_module
    from sigil.transpile.effectcheck import _admits, _budget_set, _disp, _reachable

    tree = ast.parse(source)
    budget_row = _module_fx(tree, name)
    if budget_row is None:
        return []
    budget = _budget_set(budget_row)
    facts = analyze_module(tree)
    errors = []
    for key in sorted(facts):
        if key.startswith("__sigil_"):
            continue
        for eff, (chain, reason) in sorted(_reachable(facts, key).items()):
            if not _admits(budget, eff):
                errors.append(
                    f"{name}: fn {key!r} exceeds the module __sigil_fx__ budget: "
                    f"{' -> '.join(chain)}: {reason} requires {_disp(eff)}; budget "
                    f"allows {render_row_budget(budget_row)}. Remedy: remove the "
                    "call or widen __sigil_fx__."
                )
    return errors


def render_row_budget(row: EffectRow) -> str:
    from sigil.lang.printer import pfx

    return pfx(row)


def render_sheet(
    result: LiftResult, source_path: str = "<module>", namer: DigestNamer | None = None
) -> str:
    namer = namer or DigestNamer()
    lines = [f"; digest sheet - {source_path}  (Tier 1+2 mechanical lift)"]
    body = [f"{namer.display(e.digest)} {e.name}{e.sig} {e.effects}" for e in result.entries]
    lines += body
    full = result.stats.get("source_tokens_est", 0)
    sheet = est_tokens("\n".join(body)) if body else 1
    if full:
        lines.append(
            f"; context cost: full source ~{full} tok | digest sheet ~{sheet} tok "
            f"| {full / sheet:.0f}x smaller (chars/4 estimate)"
        )
    lines.append("; '?' marks static guesses - Tier 2 over-approximates, never trusts.")
    return "\n".join(lines) + "\n"
