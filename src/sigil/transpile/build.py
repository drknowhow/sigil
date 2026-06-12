"""sigil build orchestration: parse -> transpile -> static effect check."""

from __future__ import annotations

from sigil.lang.lexer import SigilSyntaxError
from sigil.lang.parser import parse_module
from sigil.transpile.effectcheck import check_module
from sigil.transpile.python import TranspileResult, transpile_module


class BuildError(ValueError):
    """Build rejected; the message states cause + remedy (never a traceback)."""


def build_source(src: str, name: str = "<input>") -> TranspileResult:
    try:
        mod = parse_module(src)
    except SigilSyntaxError as exc:
        raise BuildError(f"sigil build: cannot parse {name}: {exc}") from exc
    result = transpile_module(mod)
    errors = check_module(mod, result.python_src)
    if errors:
        raise BuildError("sigil build: rejected.\n" + "\n".join(errors))
    return result
