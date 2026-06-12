#!/usr/bin/env python3
"""Measure real token costs (plan section 9 example 1; sigil-quality-gates:
'measured, not estimated').

Tokenizer resolution order:
1. tiktoken cl100k_base (GPT family) if importable AND its vocab is cached
2. the Claude BPE bundled with `anthropic==0.3.x` (offline, production BPE)
A run fails loudly rather than fall back to estimates.

Usage: python3 scripts/measure_costs.py  (from the repo root; prints a
markdown table and the tokenizer used — paste into docs/cost-model.md)
"""

import sys
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
        return "Claude BPE (anthropic 0.3.x bundled tokenizer.json)", lambda s: len(
            tok.encode(s).ids
        )
    except Exception:
        sys.exit(
            "No real tokenizer available. Remedy: pip install tiktoken "
            "(with network) or anthropic==0.3.11. Estimates are not acceptable "
            "for docs/cost-model.md."
        )


def main() -> None:
    name, count = get_tokenizer()
    from sigil.lift.python import lift_source, render_sheet

    rows = []

    def measure(label: str, source: str, sheet: str) -> None:
        f, s = count(source), count(sheet)
        rows.append((label, f, s, f / s))

    # 1. the seed demo module
    demo = (ROOT / "seed" / "demo_module.py").read_text()
    measure("demo_module.py (4 fns)", demo, render_sheet(lift_source(demo, "demo_module")))

    # 2. the lift-legacy flask-style app
    app = (ROOT / "examples" / "lift-legacy" / "webapp.py").read_text()
    measure("lift-legacy webapp.py (15 fns)", app, render_sheet(lift_source(app, "webapp")))

    # 3. the requests 2.34.2 snapshot (real OSS repo)
    full_parts, sheet_parts = [], []
    for f in sorted((ROOT / "tests" / "fixtures" / "oss" / "requests").glob("*.py")):
        src = f.read_text()
        full_parts.append(src)
        sheet_parts.append(render_sheet(lift_source(src, f.stem), source_path=f.name))
    measure("requests 2.34.2 (6,385 lines)", "\n".join(full_parts), "\n".join(sheet_parts))

    print(f"Tokenizer: {name}\n")
    print("| source | full source (tok) | digest sheet (tok) | reduction |")
    print("|---|---|---|---|")
    for label, f, s, ratio in rows:
        print(f"| {label} | {f:,} | {s:,} | {ratio:.1f}x |")


if __name__ == "__main__":
    main()
