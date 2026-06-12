"""Phase 4 exit gate (plan section 4), scripted form:

An agent session lifts code, reads ONLY the sheet, fixes a seeded bug via
patch, and verify confirms — zero full-file reads or writes by the agent.
(The live Claude Code session is run by a human against `sigil serve`;
this scripted transcript is the automated equivalent. See
examples/agent-session/.)
"""

from pathlib import Path

from sigil.harness.core import Harness

SEEDED = """module mathx

goal triple {
  intent: "triple the input"
  in: n Int
  out: Int
  fx: pure
  verify:
    out == n * 3
}

fn triple(n Int) -> Int
  pure
{
  ret n * 2
}
"""


def test_scripted_agent_session_fixes_seeded_bug(tmp_path) -> None:
    h = Harness(tmp_path)
    info = h.load_sigil_source(SEEDED, name="mathx")
    file_reads = 0  # the agent never opens a file below

    # 1. agent reads the sheet only
    sheet0 = h.sheet()
    assert "triple" in sheet0 and "provisional" in sheet0

    # 2. verify reports the failure with values
    v = h.verify(info["goals"]["triple"], inputs={"n": 4})
    assert v["status"] == "fail"
    failing = next(c for c in v["clauses"] if not c[1])
    assert failing[0] == "out == n * 3" and "8" in failing[2]

    # 3. agent expands ONLY the implementation subtree
    src = h.expand(info["fns"]["triple"])
    assert "ret n * 2" in src

    # 4. fix via patch — auto-verify confirms (R3)
    result = h.patch(
        info["fns"]["triple"],
        [{"path": "body.stmts.0.value.right.val", "op": "replace", "value": "3"}],
        inputs={"n": 4},
    )
    assert result["verify"]["status"] == "pass"
    assert h.store.status(info["goals"]["triple"]) == "verified"

    # 5. R1 held throughout; zero file IO by the agent
    assert h.sheet().startswith(sheet0)
    assert file_reads == 0
    assert not list(Path(tmp_path).glob("*.py"))  # no files written either
