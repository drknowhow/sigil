"""R result-hash reproducibility checks (v2.0): `analyze(seed=42) ≡ #hash`.

Requires Rscript on PATH. The R harness deparses the result deterministically;
hashing happens here. Subprocess-isolated with a timeout, like all execution.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path


def result_hash(script: str | Path, fn: str, args: list, timeout: float = 30.0) -> str:
    if shutil.which("Rscript") is None:
        raise ValueError(
            "Rscript is not on PATH. Remedy: install R (r-project.org) to run "
            "reproducibility checks; lifting .R files needs no R runtime."
        )
    r_args = ", ".join(json.dumps(a) for a in args)
    harness = (
        f"source({json.dumps(str(Path(script)))}); "
        f".sigil_res <- {fn}({r_args}); "
        f'cat(paste(deparse(.sigil_res), collapse="\\n"))'
    )
    proc = subprocess.run(
        ["Rscript", "-e", harness],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        stdin=subprocess.DEVNULL,
    )
    if proc.returncode != 0:
        raise ValueError(
            f"Rscript failed for {fn}: {proc.stderr.strip()[-300:]}. "
            "Remedy: check the function name and arguments."
        )
    return hashlib.sha256(proc.stdout.encode()).hexdigest()
