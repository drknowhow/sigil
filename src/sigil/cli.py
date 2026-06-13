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
        for ext in ("*.py", "*.R", "*.r")
        for p in path.rglob(ext)
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
            if f.suffix.lower() == ".r":
                from sigil.lift.r import lift_r_source

                result = lift_r_source(f.read_text(encoding="utf-8", errors="replace"), name=f.stem)
            else:
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
        if args.gen:
            from sigil.verify.propgen import run_property_check

            report = run_property_check(store, goal_hash, n=args.gen, timeout=args.timeout)
            print(
                json.dumps(report, indent=2)
                if args.json
                else f"property check: {report['status']} over {report['cases']} cases"
                + (
                    f"; counterexamples recorded: {len(report['counterexamples'])}"
                    if report["counterexamples"]
                    else ""
                )
            )
            return 0 if report["status"] == "pass" else 1
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


def cmd_check_r(args: argparse.Namespace) -> int:
    """R reproducibility: analyze(seed=42) must hash identically, forever."""
    from sigil.lift.rcheck import result_hash

    try:
        h = result_hash(args.script, args.fn, json.loads(args.args or "[]"), timeout=args.timeout)
    except (ValueError, subprocess_timeout()) as exc:
        print(f"sigil check-r: {exc}", file=sys.stderr)
        return 2
    print(h)
    if args.expect:
        if h == args.expect.lstrip("#"):
            print("reproducible: hash matches")
            return 0
        print(f"NOT reproducible: expected {args.expect}", file=sys.stderr)
        return 1
    return 0


def subprocess_timeout():
    import subprocess as sp

    return sp.TimeoutExpired


def cmd_migrate(args: argparse.Namespace) -> int:
    """Store v1 -> v2 (D-036): legacy objects stay readable; new lifts are IR.
    Reports which impls predate the IR so you can re-lift at leisure."""
    from sigil.core.ast import Fn, HostBlock
    from sigil.core.ir import is_ir
    from sigil.store.repo import Store

    try:
        store = Store.open(Path(args.store))
    except ValueError as exc:
        print(f"sigil migrate: {exc}", file=sys.stderr)
        return 2
    legacy = []
    for obj in store.objects.glob("*.cbor"):
        try:
            node = store.get(obj.stem)
        except Exception:  # noqa: BLE001 — survey must not die on one object
            continue
        if (
            isinstance(node, Fn)
            and isinstance(node.body, HostBlock)
            and node.body.lang == "python"
            and not is_ir(node.body.data)
        ):
            legacy.append(f"{store.display(obj.stem)} {node.name}")
    cfg = json.loads(store._config_path.read_text())
    cfg["format"] = 2
    store._config_path.write_text(json.dumps(cfg))
    print(f"store format -> 2; {len(legacy)} legacy (pre-IR) lifted objects remain readable:")
    for line in legacy:
        print(f"  {line}")
    print("Remedy when convenient: re-lift their sources; old hashes stay resolvable.")
    return 0


def cmd_from_pytest(args: argparse.Namespace) -> int:
    """Tier-3 bridge: parametrize tables -> REVIEWABLE goal drafts (never
    auto-registered)."""
    from sigil.lift.pytest_bridge import extract_drafts

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    total = 0
    for f in Path(args.path).rglob("test_*.py"):
        try:
            drafts = extract_drafts(f.read_text(encoding="utf-8"), name=f.name)
        except SyntaxError:
            continue
        for d in drafts:
            (out / f"{d['fn']}.sg.draft").write_text(d["sg"])
            (out / f"{d['fn']}.inputs.json").write_text(json.dumps(d["inputs"], indent=2))
            (out / f"{d['fn']}.cases.json").write_text(json.dumps(d["cases"], indent=2))
            total += 1
    print(f"from-pytest: {total} draft goal(s) in {out} — review, rename to .sg, build.")
    return 0 if total else 1


def cmd_check(args: argparse.Namespace) -> int:
    """CI regression gate (v1.2): rebuild every .sg, verify every goal with
    recorded inputs; --against REF also fails on silently dropped contracts."""
    import subprocess as sp
    import tempfile

    from sigil.core.ast import Goal
    from sigil.lang.parser import parse_module
    from sigil.store.repo import Store
    from sigil.transpile.build import BuildError, build_source
    from sigil.verify.runner import run_verify

    roots = [Path(p) for p in (args.paths or ["."])]
    sg_files = sorted({f for r in roots for f in ([r] if r.is_file() else r.rglob("*.sg"))})
    if not sg_files:
        print("sigil check: no .sg files found. Remedy: pass project paths.", file=sys.stderr)
        return 2
    store = Store.create(Path(tempfile.mkdtemp(prefix="sigil-check-")))
    failures = 0
    head_goals: set[str] = set()
    for f in sg_files:
        src = f.read_text(encoding="utf-8")
        try:
            build_source(src, name=str(f))
        except BuildError as exc:
            print(f"check: {f}: build rejected\n{exc}")
            failures += 1
            continue
        mod = parse_module(src)
        mh = store.put(mod)
        for d in mod.defs:
            if not isinstance(d, Goal):
                continue
            head_goals.add(d.name)
            gh = store.put(d)
            extra = {}
            if d.inputs_ref:
                extra["inputs_file"] = str(f.parent / d.inputs_ref)
            store.register_goal(gh, module_hash=mh, name=d.name, extra=extra)
            try:
                inputs = store.recorded_inputs(gh)
            except ValueError as exc:
                print(f"check: {f.name}: goal {d.name} — {exc}")
                failures += 1
                continue
            if inputs is None and d.inputs:
                print(f"check: {f.name}: goal {d.name} skipped (no recorded inputs)")
                continue
            v = run_verify(store, mod, d.name, inputs, timeout=args.timeout)
            print(f"check: {f.name}: goal {d.name} verify {v.status}")
            if v.status != "pass":
                failures += 1
    if args.against:
        base_goals: set[str] = set()
        ls = sp.run(
            ["git", "ls-tree", "-r", "--name-only", args.against],
            capture_output=True,
            text=True,
            cwd=str(roots[0]),
        )
        for rel in ls.stdout.splitlines():
            if not rel.endswith(".sg"):
                continue
            show = sp.run(
                ["git", "show", f"{args.against}:{rel}"],
                capture_output=True,
                text=True,
                cwd=str(roots[0]),
            )
            if show.returncode == 0:
                try:
                    for d in parse_module(show.stdout).defs:
                        if isinstance(d, Goal):
                            base_goals.add(d.name)
                except ValueError:
                    pass
        tombstoned = set()
        if args.store:
            try:
                ws = Store.open(Path(args.store))
                tombstoned = {e["name"] for gh, e in ws.goals().items() if ws.tombstone(gh)}
            except ValueError:
                pass
        dropped = base_goals - head_goals - tombstoned
        for name in sorted(dropped):
            print(
                f"check: goal {name} dropped since {args.against} without a "
                "tombstone (sigil unbind records intent)"
            )
            failures += 1
    if failures:
        print(f"check: FAILED ({failures} problem(s))")
        return 1
    print("check: all contracts hold")
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    from sigil.harness.watch import watch_loop

    try:
        watch_loop(args.paths or ["."], args.store, interval=args.interval)
    except KeyboardInterrupt:
        print("sigil watch: stopped.")
    return 0


def cmd_unbind(args: argparse.Namespace) -> int:
    from sigil.store.repo import Store

    try:
        store = Store.open(Path(args.store))
        goal_hash = store.resolve(args.ref)
        store.unbind(goal_hash, reason=args.reason)
    except ValueError as exc:
        print(f"sigil unbind: {exc}", file=sys.stderr)
        return 2
    print(store.describe_goal(goal_hash))
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    from sigil.store.diff import store_diff
    from sigil.store.repo import Store

    try:
        d = store_diff(Store.open(Path(args.base)), Store.open(Path(args.head)))
    except ValueError as exc:
        print(f"sigil diff: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(d, indent=2))
    else:
        marks = {"new": "+", "dropped": "-", "bound": "✓", "unbound": "✗", "retired": "†"}
        for key, items in d.items():
            for item in items:
                print(f"{marks[key]} {key}: {item}")
        if not any(d.values()):
            print("no contract changes")
    return 0 if not d["unbound"] and not d["dropped"] else 1


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
    p_verify.add_argument("--gen", type=int, help="property mode: N generated input cases")
    p_verify.add_argument("--json", action="store_true", help="machine-readable output")

    p_checkr = sub.add_parser("check-r", help="R reproducibility: result hash of fn(args)")
    p_checkr.add_argument("script", help=".R file")
    p_checkr.add_argument("--fn", required=True)
    p_checkr.add_argument("--args", help='JSON list, e.g. "[42]"')
    p_checkr.add_argument("--expect", help="expected hash (fails if different)")
    p_checkr.add_argument("--timeout", type=float, default=30.0)

    p_migrate = sub.add_parser("migrate", help="store v1 -> v2 (IR); legacy stays readable")
    p_migrate.add_argument("store", nargs="?", default=".")

    p_bridge = sub.add_parser("from-pytest", help="parametrize tables -> reviewable goal drafts")
    p_bridge.add_argument("path", help="tests directory")
    p_bridge.add_argument("--out", default="goals-proposed")

    p_check = sub.add_parser("check", help="CI gate: rebuild + re-verify every contract")
    p_check.add_argument("paths", nargs="*", help="project paths (default .)")
    p_check.add_argument("--against", help="git ref: also fail on dropped contracts")
    p_check.add_argument("--store", help="working store (tombstone exemptions)")
    p_check.add_argument("--timeout", type=float, default=10.0)
    p_check.add_argument("--json", action="store_true")

    p_watch = sub.add_parser("watch", help="save -> re-lift -> re-verify, continuously")
    p_watch.add_argument("paths", nargs="*", help="paths to watch (default .)")
    p_watch.add_argument("--store", default=".", help="store directory")
    p_watch.add_argument("--interval", type=float, default=2.0)

    p_unbind = sub.add_parser("unbind", help="retire a contract with a dated, reasoned tombstone")
    p_unbind.add_argument("ref", help="goal hash")
    p_unbind.add_argument("--reason", required=True, help="why this contract is retired")
    p_unbind.add_argument("--store", default=".", help="directory containing .sigil/")

    p_diff = sub.add_parser("diff", help="contract impact between two stores (PR review)")
    p_diff.add_argument("base", help="base store directory")
    p_diff.add_argument("head", help="head store directory")
    p_diff.add_argument("--json", action="store_true")

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
    if args.command == "check":
        return cmd_check(args)
    if args.command == "check-r":
        return cmd_check_r(args)
    if args.command == "migrate":
        return cmd_migrate(args)
    if args.command == "from-pytest":
        return cmd_from_pytest(args)
    if args.command == "watch":
        return cmd_watch(args)
    if args.command == "unbind":
        return cmd_unbind(args)
    if args.command == "diff":
        return cmd_diff(args)
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
