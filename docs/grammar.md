# Sigil text projection — grammar v1.0

Written before any `lang/` code (sigil-transpile-verify skill, step 1).
The AST is the source of truth; this text form is a *projection*. The printer
defines canonical text — one true formatting, no options. Every production is
decidable on one token of lookahead (LL(1)); expression precedence is handled
by a standard precedence climber, which preserves the LL(1) property.

## Lexical rules

- Encoding UTF-8. Spaces/tabs are insignificant. **Newlines are statement and
  clause terminators** at brace level (statements, goal fields, verify clauses,
  contracts end at end-of-line); inside `(` `)` and `[` `]` newlines are
  insignificant. An expression therefore fits on one line unless wrapped in
  parens/brackets. The canonical form is fixed by the printer.
- Comments: `--` to end of line. Comments never reach the AST (and therefore
  never affect hashes).
- `NAME`: `[A-Za-z_][A-Za-z0-9_]*`, may be dotted for qualified access in
  expression position via the `.` postfix operator (lexed as separate tokens).
- `NUMBER`: integer `[0-9]+` or float `[0-9]+.[0-9]+`. `STRING`: double-quoted,
  `\"` `\\` `\n` `\t` escapes.
- **Field tokens:** inside the lexer, the seven goal-field names
  `intent in out fx law verify ack` immediately followed by `:` lex as a single
  FIELD token. Consequence: these names are reserved before `:`; in map
  literals use string keys if a collision would occur.
- **Effect scopes:** after `!NAME(`, everything up to the matching `)` lexes as
  one raw SCOPE token (hosts and paths: `alpaca.markets`, `./cache`).

## Glyph / ASCII alias table

Parser accepts both spellings. The printer emits **ASCII** by default — it is
the canonical form: each operator is a single BPE token, where the glyph
spelling costs two (Muninn Part 2 / D-044). Glyphs can be emitted opt-in via
`printer.glyph_output()`.

| Canonical (printed) | Accepted alias | Meaning |
|---|---|---|
| `and` | `∧` | logical and |
| `or`  | `∨` | logical or |
| `not` | `¬` | logical not |
| `<=`  | `≤` | less-or-equal |
| `>=`  | `≥` | greater-or-equal |
| `!=`  | `≠` | not-equal |
| `<-`  | `←` | iteration binder |
| `->`  | `→` | return type arrow |
| `:=`  | (none) | assignment |

The spec's `⊑` (subsequence) is illustrative, not in the v1.0 core (D-011).

## Grammar (EBNF)

```
module      = "module" NAME [ "fx:" fxrow ] { item } ;   (* module-wide budget, v1.1 *)
item        = use | goal | fn ;
use         = "use" NAME ;                       (* effect-bearing Python import *)

goal        = "goal" NAME "{" { goalfield } "}" ;
goalfield   = "intent:" STRING
            | "in:"     params
            | "out:"    type
            | "fx:"     fxrow
            | "law:"    STRING
            | "ack:"    STRING                   (* required if fx contains !unsafe *)
            | "inputs:" STRING                   (* recorded-inputs file, v1.2 *)
            | "verify:" expr { expr } ;          (* clauses end at next FIELD or "}" *)

fn          = "fn" NAME "(" [ params ] ")" [ "->" type ]
              [ fxrow ] { contract } block ;
params      = param { "," param } ;
param       = NAME [ type ] ;
type        = "[" type "]"
            | NAME [ "[" type { "," type } "]" ] ;
fxrow       = "pure" | effect { effect } ;
effect      = "!" NAME [ "." NAME ] [ "(" SCOPE ")" ] [ "?" ] ;
                                                 (* mode: read | write — v1.1 *)
contract    = "pre" expr
            | "post" "|" NAME "|" expr ;         (* NAME binds the result *)

block       = "{" { stmt } "}" ;
stmt        = "ret" [ expr ]
            | "if" expr block [ "else" block ]
            | "for" NAME "<-" expr block
            | "while" expr block
            | expr [ ":=" expr ] ;               (* assignment iff ":=" follows; the
                                                    left side must be an lvalue:
                                                    NAME, attr, or index — checked
                                                    post-parse with a clear error *)

expr        = orexpr ;
orexpr      = andexpr { "∨" andexpr } ;
andexpr     = notexpr { "∧" notexpr } ;
notexpr     = "¬" notexpr | cmpexpr ;
cmpexpr     = addexpr [ cmpop addexpr ] ;        (* no chained comparisons in v1 *)
cmpop       = "==" | "≠" | "<" | "≤" | ">" | "≥" | "in" ;
addexpr     = mulexpr { ("+" | "-") mulexpr } ;
mulexpr     = powexpr { ("*" | "/" | "//" | "%") powexpr } ;
powexpr     = unary [ "**" powexpr ] ;           (* right-associative *)
unary       = "-" unary | postfix ;
postfix     = primary { "(" [ args ] ")" | "[" expr "]" | "." NAME } ;
args        = expr { "," expr } ;
primary     = NAME | NUMBER | STRING | "true" | "false" | "none"
            | "(" expr ")"
            | "[" [ expr ( "|" comp | { "," expr } ) ] "]"
            | "{" [ ":" | maporset ] "}" ;
maporset    = expr ( ":" expr { "," expr ":" expr }   (* map *)
                   | { "," expr } ) ;                  (* set *)
comp        = NAME "<-" expr { "," expr } ;      (* [elt | x <- xs, guard...] *)
```

`{}` is the empty **set**, `{:}` the empty **map** (D-012) — matching the
spec's `s := {}` set idiom in `dedupe`.

## Canonical formatting (defined by the printer)

- Two-space indentation per nesting level; goal fields at one level, verify
  clauses at two. Blank line between top-level items.
- Field order in goals: intent, in, out, fx, law (one per line), ack, verify.
- One space around binary operators and after commas; no space inside
  brackets/parens; effects separated by single spaces, sorted alphabetically.
- ASCII operators per the alias table (canonical; glyphs opt-in via
  `glyph_output()`); `--` comments are never printed (not in AST).

## Reserved words

`module use goal fn pre post ret if else for while pure true false none in
and or not` — plus the seven field names before `:`.
