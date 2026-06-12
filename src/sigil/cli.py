"""Sigil CLI. Quiet by default; --json on every command (CLAUDE.md).

Every user-facing failure states cause + remedy; no raw tracebacks.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sigil import __version__
from sigil.core.hash import DigestNamer
from sigil.lift.python import lift_source, render_sheet
from sigil.transpile.build import BuildError, build_source

_LATER_PHASES: dict[str, str] = {}


def _iter_py_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(
        p
        for p in path.rglob("*.py")
        if not any(part.startswith(".") or part == "__pycache__" for part in p.parts)
    )


def cmd_lift(args: argparse.Namespace) -> int:
    files: list[Path] = []
    for raw in args.paths:
        p = Path(raw)
        if not p.exists():
            print(
                f"sigil lift: path not found: {raw}. "
                "Remedy: check the spelling, or pass a .py file or a directory.",
                file=sys.stderr,
            )
            return 2
        files.extend(_iter_py_files(p))
    if not files:
        print(
            "sigil lift: no .py files found under the given paths. "
            "Remedy: point at a Python file or a directory containing some.",
            file=sys.stderr,
        )
        return 2

    namer = DigestNamer()
    docs, sheets, skipped = [], [], []
    for f in files:
        try:
            result = lift_source(f.read_text(encoding="utf-8", errors="replace"), name=f.stem)
        except ValueError as exc:
            skipped.append({"path": str(f), "error": str(exc)})
            continue
        docs.append(
            {
                "path": str(f),
                "module": f.stem,
                "entries": [
                    {
                        "hash": e.digest,
                        "short": namer.display(e.digest),
                        "name": e.name,
                        "sig": e.sig,
                        "effects": e.effects.split(),
                        "kind": e.kind,
                    }
                    for e in result.entries
                ],
                "stats": result.stats,
            }
        )
        sheets.append(render_sheet(result, source_path=str(f), namer=namer))

    if args.json:
        print(json.dumps({"files": docs, "skipped": skipped}, indent=2))
    else:
        print("\n".join(sheets), end="")
        for s in skipped:
            print(f"; skipped {s['path']}: {s['error']}", file=sys.stderr)
    return 0 if docs else 1


def cmd_build(args: argparse.Namespace) -> int:
    src_path = Path(args.path)
    if not src_path.exists():
        print(
            f"sigil build: file not found: {args.path}. "
            "Remedy: check the path; build expects a .sg Sigil module.",
            file=sys.stderr,
        )
        return 2
    try:
        result = build_source(src_path.read_text(encoding="utf-8"), name=str(src_path))
    except BuildError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    out_dir = Path(args.out) if args.out else src_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    goals = {}
    if args.store:
        from sigil.core.ast import Fn, Goal
        from sigil.core.hash import digest_node
        from sigil.lang.parser import parse_module
        from sigil.store.repo import Store

        store = Store.create(Path(args.store))
        mod = parse_module(src_path.read_text(encoding="utf-8"))
        module_hash = store.put(mod)
        for d in mod.defs:
            if isinstance(d, (Fn, Goal)):
                store.put(d)
            if isinstance(d, Goal):
                store.register_goal(digest_node(d), module_hash, d.name)
                goals[d.name] = digest_node(d)
    written = []
    py_path = out_dir / f"{result.module_name}.py"
    py_path.write_text(result.python_src, encoding="utf-8")
    written.append(str(py_path))
    for name, src in result.test_modules.items():
        p = out_dir / f"{name}.py"
        p.write_text(src, encoding="utf-8")
        written.append(str(p))
    if args.json:
        print(json.dumps({"module": result.module_name, "written": written, "goals": goals}))
    else:
        for w in written:
            print(f"wrote {w}")
        for name, h in goals.items():
            print(f"goal {name}: {h}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    from sigil.core.ast import Goal
    from sigil.store.repo import Store
    from sigil.verify.runner import run_verify

    try:
        store = Store.open(Path(args.store))
        goal_hash = store.resolve(args.ref)
        goal = store.get(goal_hash)
        if not isinstance(goal, Goal):
            print(
                f"sigil verify: {args.ref} is not a goal object. "
                "Remedy: pass a goal hash (see 'sigil build --store --json').",
                file=sys.stderr,
            )
            return 2
        entry = store.goals().get(goal_hash)
        if entry is None or entry.get("module") is None:
            print(
                f"sigil verify: goal {args.ref} has no registered module. "
                "Remedy: re-run 'sigil build <module.sg> --store <dir>'.",
                file=sys.stderr,
            )
            return 2
        module = store.get(entry["module"])
        inputs = json.loads(Path(args.inputs).read_text()) if args.inputs else None
        verdict = run_verify(store, module, goal.name, inputs, timeout=args.timeout)
    except ValueError as exc:
        print(f"sigil verify: {exc}", file=sys.stderr)
        return 2
    doc = {
        **verdict.to_dict(),
        "cached": verdict.cached,
        "binding": store.binding(verdict.goal_hash),
    }
    if args.json:
        print(json.dumps(doc, indent=2))
    else:
        mark = "(cached)" if verdict.cached else f"({verdict.duration_ms:.0f}ms)"
        print(f"verify {goal.name}: {verdict.status} {mark}")
        for text, ok, detail in verdict.clauses:
            print(f"  [{'ok' if ok else 'FAIL'}] {text}" + (f" — {detail}" if detail else ""))
        if verdict.detail:
            print(f"  {verdict.detail}")
        print(f"  goal status: {store.status(verdict.goal_hash)}")
    return 0 if verdict.status == "pass" else 1


def cmd_serve(args: argparse.Namespace) -> int:
    try:
        from sigil.harness.server import create_server

        server = create_server(args.root)
    except ImportError:
        print(
            "sigil serve: the 'mcp' package is not installed. "
            "Remedy: pip install 'sigil[harness]' (or pip install mcp).",
            file=sys.stderr,
        )
        return 2
    server.run()  # stdio transport; connect from Claude Code/Cowork
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sigil",
        description="Sigil: contract-first, content-addressed toolchain for human-AI coding.",
    )
    parser.add_argument("--version", action="version", version=f"sigil {__version__}")
    sub = parser.add_subparsers(dest="command")

    p_lift = sub.add_parser("lift", help="lift Python source to a Sigil digest sheet")
    p_lift.add_argument("paths", nargs="+", help=".py files or directories")
    p_lift.add_argument("--json", action="store_true", help="machine-readable output")

    p_build = sub.add_parser("build", help="transpile a .sg module to Python (static effect check)")
    p_build.add_argument("path", help="Sigil source file (.sg)")
    p_build.add_argument("--out", help="output directory (default: alongside the input)")
    p_build.add_argument("--json", action="store_true", help="machine-readable output")
    p_build.add_argument("--store", help="also register module/goals in a .sigil store at DIR")

    p_verify = sub.add_parser("verify", help="run a goal's verify clauses (cached, subprocess)")
    p_verify.add_argument("ref", help="goal hash (short #abcd or full)")
    p_verify.add_argument("--store", default=".", help="directory containing .sigil/ (default .)")
    p_verify.add_argument("--inputs", help="JSON file with the goal's input values")
    p_verify.add_argument("--timeout", type=float, default=10.0, help="seconds (default 10)")
    p_verify.add_argument("--json", action="store_true", help="machine-readable output")

    p_serve = sub.add_parser("serve", help="run the MCP harness (stdio)")
    p_serve.add_argument("--root", default=".", help="directory for the .sigil store (default .)")

    for name, phase in _LATER_PHASES.items():
        p = sub.add_parser(name, help=f"(arrives in {phase})")
        p.add_argument("args", nargs="*")
        p.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "build":
        return cmd_build(args)
    if args.command == "verify":
        return cmd_verify(args)
    if args.command == "serve":
        return cmd_serve(args)
    if args.command in _LATER_PHASES:
        print(
            f"sigil {args.command}: not available yet — it ships with "
            f"{_LATER_PHASES[args.command]} of the v1.0 build plan. "
            "Remedy: use 'sigil lift' for now, or check docs/STATUS.md for progress.",
            file=sys.stderr,
        )
        return 2
    return cmd_lift(args)


def entry() -> int:
    """Console-script entry: every failure states cause + remedy, never a traceback."""
    try:
        return main()
    except KeyboardInterrupt:
        print("sigil: interrupted.", file=sys.stderr)
        return 130
    except Exception as exc:  # noqa: BLE001 — last-resort user-facing guard
        print(
            f"sigil: unexpected error: {exc}. "
            "Remedy: re-run with the same arguments; if it persists, report it "
            "with the command line you used (this is a bug — you should never "
            "see a stack trace).",
            file=sys.stderr,
        )
        return 3


if __name__ == "__main__":
    sys.exit(entry())
