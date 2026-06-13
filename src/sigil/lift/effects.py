"""Tier 2 effect inference (sigil-effect-inference skill).

Prime directive: zero under-reporting. Over-reporting is acceptable noise;
when uncertain, emit !unsafe?, never nothing.

Algorithm:
1. Import map: dotted-path rules, longest prefix wins.
2. Origin propagation (intra-function): forward-propagate tainted origins
   through assignments; attribute access and binary ops preserve origin.
3. Call-graph propagation (inter-function): row = own effects UNION callee
   rows, iterated to fixpoint (union is monotone; cycles are fine).
4. Unresolvable (getattr dispatch, params called as functions, eval,
   unknown imports): !unsafe? — never silence.
5. !mut: global/nonlocal writes.

Origins are tagged tuples:
  ("module", "dotted.path")  imported module / from-import / builtin alias
  ("taint", "fs")            value carrying an effect capability
  ("localfn", name)          module-level function (call-graph edge)
  ("localcls", name)         module-level class
  ("param",)                 function parameter (calling one -> !unsafe?)
  ("self", clsname)          method receiver
  ("dynamic",)               unknown/dynamic value (calling one -> !unsafe?)
  None                       clean / untracked
"""

from __future__ import annotations

import ast
import builtins

from sigil.core.ast import Effect, EffectRow
from sigil.lift.rules import ANNOTATION_TAINTS, PATH_RULES

_FS_READ_METHODS = frozenset(
    {
        "read",
        "read_text",
        "read_bytes",
        "exists",
        "is_file",
        "is_dir",
        "stat",
        "iterdir",
        "glob",
        "rglob",
        "readline",
        "readlines",
        "samefile",
        "owner",
    }
)
_FS_WRITE_METHODS = frozenset(
    {
        "write",
        "write_text",
        "write_bytes",
        "mkdir",
        "unlink",
        "touch",
        "rename",
        "replace",
        "rmdir",
        "chmod",
        "symlink_to",
        "writelines",
        "truncate",
    }
)


def _match_rule(path: str) -> tuple[str | None, str | None] | None:
    parts = path.split(".")
    for i in range(len(parts), 0, -1):
        rule = PATH_RULES.get(".".join(parts[:i]))
        if rule is not None:
            return rule
    return None


class _FnAnalyzer:
    """One pass over one function body; iterated to a local fixpoint."""

    def __init__(
        self,
        module_env: dict[str, tuple],
        cls: str | None = None,
        ret_taints: dict[str, tuple | None] | None = None,
    ) -> None:
        self.module_env = module_env
        self.cls = cls
        self.ret_taints = ret_taints or {}  # fn key -> origin of its return value
        self.return_origin: tuple | None = None
        self.env: dict[str, tuple | None] = {}
        self.effects: set[tuple[str, str | None, bool]] = set()  # (name, mode, uncertain)
        self.reasons: dict[str, str] = {}  # effect name -> first source seen
        self.callees: set[str] = set()

    def emit(self, name: str, uncertain: bool, reason: str) -> None:
        base, _, mode = name.partition(".")
        self.effects.add((base, mode or None, uncertain))
        self.reasons.setdefault(base, reason.removeprefix("builtins."))

    # -- name/expression origin resolution ------------------------------
    def lookup(self, name: str) -> tuple | None:
        if name in self.env:
            return self.env[name]
        if name in self.module_env:
            return self.module_env[name]
        if hasattr(builtins, name):
            return ("module", f"builtins.{name}")
        return ("dynamic",)

    def resolve(self, e: ast.expr) -> tuple | None:
        """Origin of an expression's value; emits effects of nested calls."""
        if isinstance(e, ast.Name):
            return self.lookup(e.id)
        if isinstance(e, ast.Attribute):
            base = self.resolve(e.value)
            if base is not None and base[0] == "module":
                return ("module", f"{base[1]}.{e.attr}")
            if base is not None and base[0] == "self" and self.cls:
                return ("localfn", f"{self.cls}.{e.attr}")
            if base is not None and base[0] == "taint":
                return base
            if base is not None and base[0] == "dynamic":
                return base  # attribute of an unknown value is unknown (case_033)
            return None
        if isinstance(e, ast.Call):
            return self.eval_call(e)
        if isinstance(e, ast.Subscript):
            base = self.resolve(e.value)
            self.resolve(e.slice)
            if base is not None and base[0] == "module":
                rule = _match_rule(base[1])
                if rule:  # e.g. os.environ["HOME"] — a read IS the effect
                    if rule[0]:
                        self.emit(rule[0], False, f"{base[1]}[...]")
                    return ("taint", rule[1]) if rule[1] and rule[1] != "dynamic" else None
                self.emit("unsafe", True, f"{base[1]} (unresolved import)")
                return ("dynamic",)
            return base if base is not None and base[0] == "taint" else None
        if isinstance(e, ast.BinOp):
            lt, rt = self.resolve(e.left), self.resolve(e.right)
            for o in (lt, rt):
                if o is not None and o[0] == "taint":
                    return o
            return None
        if isinstance(e, (ast.Tuple, ast.List, ast.Set)):
            origins = [self.resolve(x) for x in e.elts]
            return next((o for o in origins if o is not None and o[0] == "taint"), None)
        if isinstance(e, ast.IfExp):
            self.resolve(e.test)
            a, b = self.resolve(e.body), self.resolve(e.orelse)
            return a if a is not None and a[0] == "taint" else b
        if isinstance(e, ast.Lambda):
            return ("dynamic",)  # calling it later is unresolvable statically
        if isinstance(e, (ast.NamedExpr,)):
            o = self.resolve(e.value)
            if isinstance(e.target, ast.Name):
                self.env[e.target.id] = o
            return o
        # Generic: recurse for effect collection, clean origin.
        for child in ast.iter_child_nodes(e):
            if isinstance(child, ast.expr):
                self.resolve(child)
            elif isinstance(child, ast.comprehension):
                self.resolve(child.iter)
                for cond in child.ifs:
                    self.resolve(cond)
        return None

    def eval_call(self, call: ast.Call) -> tuple | None:
        for a in call.args:
            self.resolve(a.value if isinstance(a, ast.Starred) else a)
        for kw in call.keywords:
            self.resolve(kw.value)
        f = self.resolve(call.func)
        if f is None:
            return None  # method on a clean local — silent (see limitations.md)
        tag = f[0]
        if tag == "module":
            if f[1] == "builtins.open":  # mode from the literal mode argument (v1.1)
                mode = "read"
                if (
                    len(call.args) >= 2
                    and isinstance(call.args[1], ast.Constant)
                    and isinstance(call.args[1].value, str)
                ):
                    mode = "write" if any(c in call.args[1].value for c in "wax+") else "read"
                elif len(call.args) >= 2 or call.keywords:
                    mode = ""  # can't see the mode: unmoded superset, never under-report
                self.emit(f"fs.{mode}" if mode else "fs", False, "open")
                return ("taint", "fs")
            rule = _match_rule(f[1])
            if rule is None:  # unknown import — never silence
                self.emit("unsafe", True, f"{f[1]} (unresolved import)")
                return ("dynamic",)
            emit, taint = rule
            if emit:
                self.emit(emit, False, f[1])
            if taint == "dynamic":
                return ("dynamic",)
            return ("taint", taint) if taint else None
        if tag == "taint":
            eff = f[1]
            if eff == "fs" and isinstance(call.func, ast.Attribute):
                m = call.func.attr
                if m in _FS_READ_METHODS:
                    eff = "fs.read"
                elif m in _FS_WRITE_METHODS:
                    eff = "fs.write"
            self.emit(eff, False, f"call on !{f[1]}-capable value")
            return f
        if tag == "localfn":
            self.callees.add(f[1])
            # Return-taint propagation (fixtures case_032/033): a helper that
            # returns a Path-like or dynamic value taints its caller's use.
            return self.ret_taints.get(f[1])
        if tag == "localcls":
            return None
        if tag in ("param", "dynamic"):
            self.emit("unsafe", True, "dynamic call (unresolvable statically)")
            return ("dynamic",)
        if tag == "self":
            return None
        return None

    # -- statements ------------------------------------------------------
    def exec_stmt(self, s: ast.stmt) -> None:
        if isinstance(s, (ast.Global, ast.Nonlocal)):
            self.emit("mut", False, "global/nonlocal write")
        elif isinstance(s, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            value = s.value
            origin = self.resolve(value) if value is not None else None
            targets = s.targets if isinstance(s, ast.Assign) else [s.target]
            for t in targets:
                if isinstance(t, ast.Name):
                    self.env[t.id] = origin
                else:
                    self.resolve(t)
        elif isinstance(s, (ast.With, ast.AsyncWith)):
            for item in s.items:
                origin = self.resolve(item.context_expr)
                if item.optional_vars is not None and isinstance(item.optional_vars, ast.Name):
                    self.env[item.optional_vars.id] = origin
            for sub in s.body:
                self.exec_stmt(sub)
        elif isinstance(s, (ast.For, ast.AsyncFor)):
            self.resolve(s.iter)
            for sub in s.body + s.orelse:
                self.exec_stmt(sub)
        elif isinstance(s, (ast.While, ast.If)):
            self.resolve(s.test)
            for sub in s.body + s.orelse:
                self.exec_stmt(sub)
        elif isinstance(s, ast.Try):
            for sub in s.body + s.orelse + s.finalbody:
                self.exec_stmt(sub)
            for h in s.handlers:
                for sub in h.body:
                    self.exec_stmt(sub)
        elif isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Nested defs: their effects surface when called; conservatively
            # fold them into the enclosing function (PoC behavior).
            for sub in s.body:
                self.exec_stmt(sub)
            self.env[s.name] = ("dynamic",)
        elif isinstance(s, ast.Return):
            if s.value is not None:
                origin = self.resolve(s.value)
                tracked = origin is not None and origin[0] in ("taint", "dynamic", "module")
                if tracked and self.return_origin is None:
                    self.return_origin = origin
        elif isinstance(s, ast.Expr):
            if s.value is not None:
                self.resolve(s.value)
        elif isinstance(s, (ast.Raise,)):
            if s.exc is not None:
                self.resolve(s.exc)
        elif isinstance(s, ast.Delete):
            pass
        else:
            for child in ast.iter_child_nodes(s):
                if isinstance(child, ast.expr):
                    self.resolve(child)
                elif isinstance(child, ast.stmt):
                    self.exec_stmt(child)

    def run(self, fn: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        args = fn.args
        for a in [
            *args.posonlyargs,
            *args.args,
            *args.kwonlyargs,
            *([args.vararg] if args.vararg else []),
            *([args.kwarg] if args.kwarg else []),
        ]:
            self.env[a.arg] = self._param_origin(a)
        if self.cls and (args.posonlyargs or args.args):
            first = (args.posonlyargs or args.args)[0]
            self.env[first.arg] = ("self", self.cls)
        # Local fixpoint: loops can use names assigned later in the body.
        for _ in range(4):
            before = (len(self.effects), dict(self.env), set(self.callees))
            for s in fn.body:
                self.exec_stmt(s)
            if (len(self.effects), self.env, self.callees) == before:
                break

    def _param_origin(self, a: ast.arg) -> tuple:
        if a.annotation is not None:
            o = self.resolve(a.annotation)
            if o is not None and o[0] == "module":
                taint = ANNOTATION_TAINTS.get(o[1]) or ANNOTATION_TAINTS.get(
                    o[1].removeprefix("builtins.")
                )
                if taint is None:
                    rule = _match_rule(o[1])
                    if rule and rule[1] and rule[1] != "dynamic":
                        taint = rule[1]
                if taint:
                    return ("taint", taint)
        return ("param",)


def build_module_env(tree: ast.Module) -> dict[str, tuple]:
    env: dict[str, tuple] = {}
    for s in tree.body:
        if isinstance(s, ast.Import):
            for alias in s.names:
                name = alias.asname or alias.name.split(".")[0]
                env[name] = ("module", alias.name if alias.asname else alias.name.split(".")[0])
        elif isinstance(s, ast.ImportFrom):
            mod = ("." * s.level) + (s.module or "")
            for alias in s.names:
                env[alias.asname or alias.name] = ("module", f"{mod}.{alias.name}")
        elif isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)):
            env[s.name] = ("localfn", s.name)
        elif isinstance(s, ast.ClassDef):
            env[s.name] = ("localcls", s.name)
    # Module-level assignments (e.g. CACHE = Path("./cache")) — two passes
    # so later constants may reference earlier ones.
    for _ in range(2):
        scratch = _FnAnalyzer(env)
        for s in tree.body:
            if isinstance(s, (ast.Assign, ast.AnnAssign)) and s.value is not None:
                origin = scratch.resolve(s.value)
                targets = s.targets if isinstance(s, ast.Assign) else [s.target]
                for t in targets:
                    if isinstance(t, ast.Name):
                        env[t.id] = origin if origin is not None else env.get(t.id)
        env = {k: v for k, v in env.items() if v is not None}
    return env


class FnFacts:
    """Per-function analysis facts: own effects, their sources, callees."""

    def __init__(
        self, effects: set[tuple[str, bool]], reasons: dict[str, str], callees: set[str]
    ) -> None:
        self.effects = effects
        self.reasons = reasons
        self.callees = callees


def analyze_module(tree: ast.Module) -> dict[str, FnFacts]:
    """Own-effect facts per function/method, pre-fixpoint. One analyzer, two
    callers: the lifter's rows and the transpiler's budget check (skill rule).

    Runs in rounds so return taints flow through local helper calls
    (fixtures case_032/033): round N+1 sees round N's return origins."""
    env = build_module_env(tree)
    targets: list[tuple] = []
    for s in tree.body:
        if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)):
            targets.append((s, s.name, None))
        elif isinstance(s, ast.ClassDef):
            for m in s.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    targets.append((m, f"{s.name}.{m.name}", s.name))

    ret_taints: dict[str, tuple | None] = {}
    out: dict[str, FnFacts] = {}
    for _round in range(3):
        out = {}
        new_taints: dict[str, tuple | None] = {}
        for fn, key, cls in targets:
            a = _FnAnalyzer(env, cls=cls, ret_taints=ret_taints)
            a.run(fn)
            out[key] = FnFacts(a.effects, a.reasons, a.callees)
            new_taints[key] = a.return_origin
        if new_taints == ret_taints:
            break
        ret_taints = new_taints
    return out


def infer_module_effects(tree: ast.Module) -> dict[str, EffectRow]:
    """Effect rows for every module-level function and class method,
    keyed by name ('fn' or 'Cls.method'), after call-graph fixpoint."""
    facts = analyze_module(tree)
    own = {k: f.effects for k, f in facts.items()}
    callees = {k: f.callees for k, f in facts.items()}

    rows: dict[str, set[tuple[str, bool]]] = {k: set(v) for k, v in own.items()}
    changed = True
    while changed:  # monotone union -> terminates
        changed = False
        for k, calls in callees.items():
            for c in calls:
                if c in rows and not rows[c] <= rows[k]:
                    rows[k] |= rows[c]
                    changed = True

    out: dict[str, EffectRow] = {}
    for k, fx in rows.items():
        by_name: dict[str, dict] = {}
        for name, mode, uncertain in fx:
            slot = by_name.setdefault(name, {"modes": set(), "uncertain": True})
            slot["modes"].add(mode)
            slot["uncertain"] = slot["uncertain"] and uncertain  # certain wins
        effects = []
        for name in sorted(by_name):
            modes, unc = by_name[name]["modes"], by_name[name]["uncertain"]
            if None in modes or {"read", "write"} <= modes:
                effects.append(Effect(name=name, scope=None, uncertain=unc, mode=None))
            else:
                for m in sorted(modes):
                    effects.append(Effect(name=name, scope=None, uncertain=unc, mode=m))
        out[k] = EffectRow(effects=effects, uncertain=True)  # Tier 2 = static guess
    return out


def render_row(row: EffectRow) -> str:
    if not row.effects:
        return "pure?" if row.uncertain else "pure"
    return " ".join(
        f"!{e.name}{'.' + e.mode if e.mode else ''}{'?' if e.uncertain else ''}"
        for e in row.effects
    )
