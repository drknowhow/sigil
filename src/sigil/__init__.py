"""Sigil — contract-first, content-addressed language + toolchain for human-AI coding."""

__version__ = "1.1.0"

from sigil._bind import SigilBindError, bind, verify_bound  # noqa: E402

__all__ = ["bind", "verify_bound", "SigilBindError", "__version__"]
