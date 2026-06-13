"""Phase 1 exit gate (plan section 4): lift a real 3k+ line OSS repo.

Snapshot: requests 2.34.2 (tests/fixtures/oss/requests, Apache-2.0).
Spot-check record: tests/fixtures/oss/spotcheck-2026-06-11.md —
2/30 under-reports found (6.7% < 10% gate); the os.path.exists miss became
fixture case_031 and is fixed; the untracked-local gap is documented in
decisions.md D-008.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
OSS = ROOT / "tests" / "fixtures" / "oss" / "requests"
GOLDEN = ROOT / "tests" / "golden" / "requests.sheet"


def test_snapshot_is_3k_plus_lines() -> None:
    total = sum(len(p.read_text().splitlines()) for p in OSS.glob("*.py"))
    assert total >= 3000, f"snapshot too small: {total} lines"


def test_lift_oss_repo_generates_sheet_verbatim() -> None:
    r = subprocess.run(
        [sys.executable, "-m", "sigil.cli", "lift", "tests/fixtures/oss/requests"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        env={"PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert r.returncode == 0, r.stderr
    assert r.stderr == ""  # no skipped files
    digest_lines = [ln for ln in r.stdout.splitlines() if ln.startswith("#")]
    assert len(digest_lines) >= 250
    # Golden: byte-exact on the generating Python minor; off-version assert
    # structure only (D-002 — lifted host-AST digests shift across minors;
    # the firstuse V2_REPORT saw exactly this on Python 3.14).
    pyver = GOLDEN.with_suffix(".sheet.pyver")
    gen = pyver.read_text().strip() if pyver.exists() else "3.10"
    here = f"{sys.version_info.major}.{sys.version_info.minor}"
    if here == gen:
        assert r.stdout == GOLDEN.read_text()
    else:
        want = [ln for ln in GOLDEN.read_text().splitlines() if ln.startswith("#")]
        assert len(digest_lines) == len(want)
        assert [ln.split()[1] for ln in digest_lines] == [ln.split()[1] for ln in want]


def test_spotcheck_findings_are_fixed() -> None:
    sheet = GOLDEN.read_text()
    cert_verify = next(ln for ln in sheet.splitlines() if " HTTPAdapter.cert_verify" in ln)
    assert "!fs" in cert_verify, "os.path.exists under-report regressed (case_031)"
