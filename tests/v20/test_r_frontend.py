"""v2.0 gate: R frontend — Tier-1 hashing + effect-lite rows; runner optional."""

import shutil

import pytest

from sigil.lift.r import lift_r_source

R_SRC = """
# analysis pipeline
analyze <- function(path, seed) {
  set.seed(seed)  # reproducibility
  df <- read.csv(path)
  m <- mean(df$value) + rnorm(1)
  m
}

pure_helper <- function(x, y) {
  (x + y) / 2
}

fetchy <- function(u) {
  download.file(u, "tmp.bin")
  Sys.time()
}
"""


def test_r_lift_finds_functions_and_effects() -> None:
    r = lift_r_source(R_SRC, name="analysis")
    rows = {e.name: e.effects for e in r.entries}
    assert set(rows) == {"analyze", "pure_helper", "fetchy"}
    assert "!fs.read" in rows["analyze"] and "!rand" in rows["analyze"]
    assert rows["pure_helper"] == "pure?"
    assert "!net" in rows["fetchy"] and "!clock" in rows["fetchy"]


def test_r_hash_ignores_comments_and_whitespace() -> None:
    a = lift_r_source(R_SRC)
    noisy = R_SRC.replace("set.seed(seed)", "set.seed( seed )   # tweak")
    noisy = "# header comment\n\n" + noisy.replace("\n}", "\n  }\n")
    b = lift_r_source(noisy)
    assert {e.name: e.digest for e in a.entries} == {e.name: e.digest for e in b.entries}
    changed = lift_r_source(R_SRC.replace("(x + y) / 2", "(x + y) / 3"))
    assert {e.name: e.digest for e in a.entries} != {e.name: e.digest for e in changed.entries}


def test_library_loads_are_flagged_unsafe() -> None:
    src = "f <- function(x) {\n  library(dplyr)\n  x\n}\n"
    r = lift_r_source(src)
    assert "!unsafe" in r.entries[0].effects


@pytest.mark.skipif(shutil.which("Rscript") is None, reason="Rscript not available")
def test_check_r_reproducibility(tmp_path) -> None:
    from sigil.lift.rcheck import result_hash

    script = tmp_path / "a.R"
    script.write_text("analyze <- function(seed) {\n  set.seed(seed)\n  runif(3)\n}\n")
    h1 = result_hash(script, "analyze", [42])
    h2 = result_hash(script, "analyze", [42])
    assert h1 == h2  # the reproducibility contract: same seed, same hash
