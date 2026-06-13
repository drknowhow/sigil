"""Static effect-budget check: subset rule, golden chain message, !unsafe ack."""

import textwrap

import pytest

from sigil.transpile.build import BuildError, build_source

OVER_BUDGET = """module prices

use requests

goal fetch_prices {
  intent: "fetch with cache"
  in: tickers [Str]
  out: Map
  fx: !net(api.example.com)
  verify:
    out.keys.set == tickers.set
}

fn fetch_prices(tickers [Str]) -> Map
  !net(api.example.com) !fs(./cache)
{
  out := {:}
  for t <- tickers {
    r := requests.get("https://api.example.com/v2/bars/" + t)
    out[t] := r.json()
    save_cache(t, r.text)
  }
  ret out
}

fn save_cache(t Str, data Str)
  !fs(./cache)
{
  f := open("./cache/" + t, "w")
  f.write(data)
}
"""


def test_over_budget_effect_rejected_with_chain() -> None:
    with pytest.raises(BuildError) as exc:
        build_source(OVER_BUDGET)
    msg = str(exc.value)
    # Golden chain line (sigil-transpile-verify skill: message has a golden test).
    assert (
        "fetch_prices -> save_cache: open requires !fs.write; budget allows !net(api.example.com)"
        in msg
    )
    assert "Remedy" in msg


def test_within_budget_builds() -> None:
    ok = OVER_BUDGET.replace(
        "fx: !net(api.example.com)\n", "fx: !fs(./cache) !net(api.example.com)\n"
    )
    result = build_source(ok)
    assert "def fetch_prices" in result.python_src


def test_fn_declared_pure_but_effectful_rejected() -> None:
    src = textwrap.dedent("""\
    module m

    fn sneaky(path Str) -> Str
      pure
    {
      ret open(path).read()
    }
    """)
    with pytest.raises(BuildError, match="(?s)sneaky.*declares.*pure.*!fs.*Remedy"):
        build_source(src)


def test_unsafe_budget_requires_ack() -> None:
    src = textwrap.dedent("""\
    module m

    use subprocess

    goal runner {
      intent: "run a tool"
      in: cmd Str
      out: Str
      fx: !unsafe
      verify:
        out.len ≥ 0
    }

    fn runner(cmd Str) -> Str
      !unsafe
    {
      ret subprocess.run(cmd)
    }
    """)
    with pytest.raises(BuildError, match="(?s)!unsafe.*ack.*Remedy"):
        build_source(src)
    acked = src.replace("fx: !unsafe\n", 'fx: !unsafe\n  ack: "vetted: demo tool runner"\n')
    assert build_source(acked).python_src


def test_undeclared_fn_row_is_inferred_not_checked() -> None:
    src = textwrap.dedent("""\
    module m

    fn free(path Str) -> Str
    {
      ret open(path).read()
    }
    """)
    assert "def free" in build_source(src).python_src
