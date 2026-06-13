#!/usr/bin/env python3
"""Benchmark suite for Sigil (v2.0.1). Measured, not estimated — every number
here is produced from the actual package + artifacts in this repo.

Run from the repo root: python3 scripts/benchmark.py [--json]

Tokenizer: real production BPE (Claude's, bundled offline with anthropic 0.3.x;
prefers tiktoken cl100k_base when its vocab is cached). Refuses to fall back to
chars/4 estimates for the context-cost numbers.
"""

from __future__ import annotations

import json
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.dont_write_bytecode = True


def get_tokenizer():
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        return "tiktoken cl100k_base (GPT family)", lambda s: len(enc.encode(s))
    except Exception:
        pass
    try:
        from anthropic._tokenizers import sync_get_tokenizer

        tok = sync_get_tokenizer()
        return "Claude BPE (anthropic 0.3.x bundled)", lambda s: len(tok.encode(s).ids)
    except Exception:
        sys.exit("No real tokenizer available (need tiktoken or anthropic==0.3.x). "
                 "Estimates are not acceptable for context-cost numbers.")


def bench_context_reduction(count) -> list[dict]:
    from sigil.lift.python import lift_source, render_sheet

    rows = []

    def one(label, source, sheet):
        f, s = count(source), count(sheet)
        rows.append({"source": label, "full_tokens": f, "sheet_tokens": s,
                     "reduction": round(f / s, 1)})

    demo = (ROOT / "seed" / "demo_module.py").read_text()
    one("demo_module.py (4 fns)", demo, render_sheet(lift_source(demo, "demo")))
    app = (ROOT / "examples" / "lift-legacy" / "webapp.py").read_text()
    one("lift-legacy webapp.py (15 fns)", app, render_sheet(lift_source(app, "webapp")))
    full, sheet = [], []
    for fpath in sorted((ROOT / "tests/fixtures/oss/requests").glob("*.py")):
        src = fpath.read_text()
        full.append(src)
        sheet.append(render_sheet(lift_source(src, fpath.stem), source_path=fpath.name))
    one("requests 2.34.2 (6,385 lines)", "\n".join(full), "\n".join(sheet))
    return rows


def bench_iteration(count) -> dict:
    """One agent turn: re-read sheet (cached) + expand one fn + emit a patch,
    vs re-reading the whole module fresh."""
    from sigil.harness.core import Harness

    sg = (
        "module mathx\n\ngoal triple {\n  intent: \"triples\"\n  in: n Int\n"
        "  out: Int\n  fx: pure\n  verify:\n    out == n * 3\n}\n\n"
        "fn triple(n Int) -> Int\n  pure\n{\n  ret n * 2\n}\n"
    )
    with tempfile.TemporaryDirectory() as tmp:
        h = Harness(tmp)
        info = h.load_sigil_source(sg, name="mathx")
        sheet = h.sheet()
        impl = h.expand(info["fns"]["triple"])
        patch_op = json.dumps({"path": "body.stmts.0.value.right.val",
                               "op": "replace", "value": "3"})
    return {"full_module_tokens": count(sg), "sheet_tokens": count(sheet),
            "expand_one_fn_tokens": count(impl), "patch_output_tokens": count(patch_op)}


def bench_verify_cache() -> dict:
    """Cold verify (subprocess) vs cached verify (store hit). Median of runs."""
    from sigil.lang.parser import parse_module
    from sigil.store.repo import Store
    from sigil.verify.runner import run_verify

    sg = (
        "module m\n\ngoal sq {\n  intent: \"square\"\n  in: n Int\n  out: Int\n"
        "  fx: pure\n  verify:\n    out == n * n\n}\n\n"
        "fn sq(n Int) -> Int\n  pure\n{\n  ret n * n\n}\n"
    )
    mod = parse_module(sg)
    cold, hot = [], []
    for i in range(7):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store.create(tmp)
            t0 = time.perf_counter()
            run_verify(store, mod, "sq", inputs={"n": i + 2})
            cold.append((time.perf_counter() - t0) * 1000)
            t1 = time.perf_counter()
            v = run_verify(store, mod, "sq", inputs={"n": i + 2})
            hot.append((time.perf_counter() - t1) * 1000)
            assert v.cached
    return {"cold_ms_median": round(statistics.median(cold), 1),
            "cached_ms_median": round(statistics.median(hot), 2),
            "speedup": round(statistics.median(cold) / statistics.median(hot))}


def bench_effects() -> dict:
    """Under-report / over-report on the hand-labeled fixture set."""
    import ast as pyast

    from sigil.lift.effects import infer_module_effects

    fixtures = sorted((ROOT / "tests/fixtures/effects").glob("case_*.py"))
    under = over = labeled = total_funcs = 0
    for case in fixtures:
        labels = json.loads(case.with_suffix("").with_suffix(".labels.json").read_text())
        rows = infer_module_effects(pyast.parse(case.read_text()))
        for fn, expected in labels.items():
            total_funcs += 1
            inferred = {e.name for e in rows[fn].effects}
            bases = {lbl.lstrip("!").rstrip("?") for lbl in expected if lbl != "pure"}
            labeled += len(bases) or 1
            for b in bases:
                if b not in inferred and "unsafe" not in inferred:
                    under += 1
            extra = inferred - bases - {"unsafe"}
            over += len(extra)
    return {"fixtures": len(fixtures), "labeled_functions": total_funcs,
            "under_reports": under, "over_report_rate_pct": round(100 * over / labeled, 1)}


def bench_lift_throughput() -> dict:
    """Lift speed on the requests snapshot (definitions/sec)."""
    from sigil.lift.python import lift_source

    files = sorted((ROOT / "tests/fixtures/oss/requests").glob("*.py"))
    srcs = [f.read_text() for f in files]
    defs = 0
    t0 = time.perf_counter()
    for i, src in enumerate(srcs):
        defs += len(lift_source(src, files[i].stem).entries)
    dt = time.perf_counter() - t0
    lines = sum(len(s.splitlines()) for s in srcs)
    return {"lines": lines, "definitions": defs, "seconds": round(dt, 3),
            "defs_per_sec": round(defs / dt), "lines_per_sec": round(lines / dt)}


def bench_ir_roundtrip() -> dict:
    """IR lower -> render -> re-lower is hash-stable across the OSS snapshot."""
    import ast as pyast

    from sigil.core.hash import digest_data
    from sigil.core.ir import ir_source, lower_module

    files = sorted((ROOT / "tests/fixtures/oss/requests").glob("*.py"))
    stable = checked = 0
    for f in files:
        ir = lower_module(pyast.parse(f.read_text()))
        if digest_data(lower_module(pyast.parse(ir_source(ir)))) == digest_data(ir):
            stable += 1
        checked += 1
    return {"modules_checked": checked, "roundtrip_stable": stable,
            "stable_pct": round(100 * stable / checked, 1)}


def main() -> None:
    name, count = get_tokenizer()
    result = {
        "version": "2.0.1",
        "tokenizer": name,
        "context_reduction": bench_context_reduction(count),
        "iteration_turn": bench_iteration(count),
        "verify_cache": bench_verify_cache(),
        "effect_inference": bench_effects(),
        "lift_throughput": bench_lift_throughput(),
        "ir_roundtrip": bench_ir_roundtrip(),
    }
    if "--json" in sys.argv:
        print(json.dumps(result, indent=2))
        return
    print(f"Sigil v{result['version']} benchmark  ·  tokenizer: {name}\n")
    print("Context reduction (first contact):")
    for r in result["context_reduction"]:
        print(f"  {r['source']:36s} {r['full_tokens']:>7,} -> {r['sheet_tokens']:>6,} tok"
              f"  ({r['reduction']}x)")
    it = result["iteration_turn"]
    print(f"\nIteration turn: sheet {it['sheet_tokens']} tok (cached) · "
          f"expand 1 fn {it['expand_one_fn_tokens']} tok · "
          f"patch {it['patch_output_tokens']} tok out · "
          f"vs full module {it['full_module_tokens']} tok")
    vc = result["verify_cache"]
    print(f"\nVerify: cold {vc['cold_ms_median']} ms · cached {vc['cached_ms_median']} ms "
          f"({vc['speedup']}x faster on a hit)")
    ef = result["effect_inference"]
    print(f"\nEffect inference: {ef['under_reports']} under-reports across "
          f"{ef['labeled_functions']} labeled fns ({ef['fixtures']} fixtures); "
          f"{ef['over_report_rate_pct']}% over-report")
    lt = result["lift_throughput"]
    print(f"\nLift throughput: {lt['definitions']} defs / {lt['lines']:,} lines in "
          f"{lt['seconds']}s = {lt['defs_per_sec']:,} defs/s ({lt['lines_per_sec']:,} lines/s)")
    rt = result["ir_roundtrip"]
    print(f"\nIR round-trip: {rt['roundtrip_stable']}/{rt['modules_checked']} modules "
          f"hash-stable ({rt['stable_pct']}%)")




def write_plots() -> None:
    """Regenerate docs/img/*.svg from the live numbers (needs matplotlib)."""
    try:
        import matplotlib
    except ImportError:
        sys.exit("matplotlib not installed. Remedy: pip install matplotlib, or use "
                 "the live charts on the hero page (site/index.html).")
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out = ROOT / "docs" / "img"
    out.mkdir(parents=True, exist_ok=True)
    BG, PANEL, TXT, DIM, LINE = "#0b0f18", "#0b0f18", "#e8ecf4", "#8b94a7", "#2a3140"
    CY, VI = "#5eead4", "#a78bfa"

    def ax_style(ax):
        ax.set_facecolor(PANEL)
        for sp in ax.spines.values():
            sp.set_color(LINE)
        ax.tick_params(colors=DIM, labelsize=9)
        ax.grid(axis="y", color=LINE, lw=0.6, alpha=0.5)

    name, count = get_tokenizer()
    cr = {r["source"]: r for r in bench_context_reduction(count)}
    # reduction
    f, ax = plt.subplots(figsize=(7.2, 3.4), dpi=130)
    f.patch.set_facecolor(BG)
    ax_style(ax)
    labels, pct, ann = [], [], []
    for key in ["requests 2.34.2 (6,385 lines)", "lift-legacy webapp.py (15 fns)",
                "demo_module.py (4 fns)"]:
        r = cr[key]
        labels.append(key.split(" (")[0])
        pct.append(r["sheet_tokens"] / r["full_tokens"] * 100)
        ann.append(f"{r['reduction']}x  ({r['full_tokens']:,}->{r['sheet_tokens']:,})")
    ax.barh(labels, [100] * len(labels), color="#1a2030", height=0.55)
    ax.barh(labels, pct, color=[CY, VI, VI], height=0.55)
    for i, (p, a) in enumerate(zip(pct, ann, strict=True)):
        ax.text(p + 2, i, a, va="center", color=TXT, fontsize=9, fontweight="bold")
    ax.set_xlim(0, 140)
    ax.invert_yaxis()
    ax.set_title("Context reduction - sheet vs full source", loc="left", color=TXT,
                 fontsize=12, fontweight="bold")
    f.tight_layout()
    f.savefig(out / "bench-reduction.svg", facecolor=BG)
    plt.close(f)
    print(f"wrote {out}/bench-reduction.svg (+ run the full generator for the rest)")


if __name__ == "__main__":
    if "--plots" in sys.argv:
        write_plots()
    else:
        main()
