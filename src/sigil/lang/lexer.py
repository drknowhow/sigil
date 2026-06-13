"""Lexer for the Sigil text projection. Grammar: docs/grammar.md.

Glyphs normalize to their ASCII alias at lex time (parser sees one spelling).
Comments (-- to end of line) are dropped here and never reach the AST.
"""

from __future__ import annotations

from dataclasses import dataclass

GLYPHS = {"∧": "and", "∨": "or", "¬": "not", "≤": "<=", "≥": ">=", "≠": "!=", "←": "<-", "→": "->"}
KEYWORDS = {
    "module",
    "use",
    "goal",
    "fn",
    "pre",
    "post",
    "ret",
    "if",
    "else",
    "for",
    "while",
    "pure",
    "true",
    "false",
    "none",
    "in",
    "and",
    "or",
    "not",
}
FIELDS = {"intent", "in", "out", "fx", "law", "verify", "ack", "inputs", "over"}
TWO_CHAR = [":=", "<-", "->", "==", "!=", "<=", ">=", "//", "**"]
ONE_CHAR = "{}()[],:|!?.+-*/%<>="
ESCAPES = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}


@dataclass(frozen=True)
class Tok:
    kind: str  # NAME NUMBER STRING FIELD SCOPE KW OP EOF
    val: str
    line: int
    col: int


class SigilSyntaxError(ValueError):
    def __init__(self, msg: str, line: int, col: int, remedy: str) -> None:
        super().__init__(
            f"Sigil syntax error at line {line}, column {col}: {msg}. Remedy: {remedy}"
        )
        self.line, self.col = line, col


def tokenize(src: str) -> list[Tok]:
    toks: list[Tok] = []
    i, line, col = 0, 1, 1
    depth = 0  # () and [] nesting; newlines are insignificant inside
    n = len(src)

    def err(msg: str, remedy: str) -> SigilSyntaxError:
        return SigilSyntaxError(msg, line, col, remedy)

    def emit(kind: str, val: str) -> None:
        toks.append(Tok(kind, val, line, col))

    while i < n:
        c = src[i]
        if c == "\n":
            if depth == 0 and toks and toks[-1].kind != "NL":
                emit("NL", "")
            i += 1
            line += 1
            col = 1
            continue
        if c in " \t\r":
            i += 1
            col += 1
            continue
        if src.startswith("--", i):
            while i < n and src[i] != "\n":
                i += 1
            continue
        if c in GLYPHS:
            alias = GLYPHS[c]
            emit("KW" if alias in KEYWORDS else "OP", alias)
            i += 1
            col += 1
            continue
        if c == '"':
            start_line, start_col = line, col
            i += 1
            col += 1
            out = []
            while True:
                if i >= n or src[i] == "\n":
                    raise SigilSyntaxError(
                        "unterminated string", start_line, start_col, 'close the string with "'
                    )
                ch = src[i]
                if ch == "\\":
                    if i + 1 >= n or src[i + 1] not in ESCAPES:
                        raise err("bad string escape", 'use \\\\ \\" \\n or \\t')
                    out.append(ESCAPES[src[i + 1]])
                    i += 2
                    col += 2
                    continue
                if ch == '"':
                    i += 1
                    col += 1
                    break
                out.append(ch)
                i += 1
                col += 1
            emit("STRING", "".join(out))
            continue
        if c.isdigit():
            j = i
            while j < n and src[j].isdigit():
                j += 1
            if j < n and src[j] == "." and j + 1 < n and src[j + 1].isdigit():
                j += 1
                while j < n and src[j].isdigit():
                    j += 1
            emit("NUMBER", src[i:j])
            col += j - i
            i = j
            continue
        if c.isalpha() or c == "_":
            j = i
            while j < n and (src[j].isalnum() or src[j] == "_"):
                j += 1
            word = src[i:j]
            if word in FIELDS and j < n and src[j] == ":":
                emit("FIELD", word)
                j += 1
            elif word in KEYWORDS:
                emit("KW", word)
            else:
                emit("NAME", word)
            col += j - i
            i = j
            continue
        # Effect scope: after '!' NAME [ '.' NAME ] '(' raw up to ')'.
        if (
            c == "("
            and len(toks) >= 2
            and toks[-1].kind == "NAME"
            and (
                (toks[-2].kind == "OP" and toks[-2].val == "!")
                or (
                    len(toks) >= 4
                    and toks[-2].kind == "OP"
                    and toks[-2].val == "."
                    and toks[-3].kind == "NAME"
                    and toks[-4].kind == "OP"
                    and toks[-4].val == "!"
                )
            )
        ):
            emit("OP", "(")
            depth += 1
            i += 1
            col += 1
            j = src.find(")", i)
            if j == -1:
                raise err("unterminated effect scope", "close the scope with )")
            emit("SCOPE", src[i:j].strip())
            col += j - i
            i = j
            continue
        two = src[i : i + 2]
        if two in TWO_CHAR:
            emit("OP", two)
            i += 2
            col += 2
            continue
        if c in ONE_CHAR:
            if c in "([":
                depth += 1
            elif c in ")]":
                depth = max(0, depth - 1)
            emit("OP", c)
            i += 1
            col += 1
            continue
        raise err(f"unexpected character {c!r}", "check docs/grammar.md for the allowed syntax")
    while toks and toks[-1].kind == "NL":
        toks.pop()
    toks.append(Tok("EOF", "", line, col))
    return toks
