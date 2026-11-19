"""Turn Python source code into named facts, and compare two versions.

A "fact" is something documentation can talk about: a function and its
parameters, a class, a module constant, or a command-line flag. Comparing the
facts of the old and new version of a file tells us what changed in meaning,
not just which lines changed.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

FLAG_METHODS = {"add_argument", "option"}  # argparse and click

# Change kinds, from most to least certain.
REMOVED = "REMOVED"
RENAMED = "RENAMED"
SIGNATURE_CHANGED = "SIGNATURE_CHANGED"
DEFAULT_CHANGED = "DEFAULT_CHANGED"
HELP_OR_BODY_CHANGED = "HELP_OR_BODY_CHANGED"


@dataclass(frozen=True)
class Fact:
    """One documentable thing found in a file."""

    kind: str  # "function", "class", "constant" or "flag"
    name: str  # e.g. "connect", "Client.send", "TIMEOUT", "--max-retries"
    line: int
    params: tuple[str, ...] = ()  # functions only, in order
    defaults: tuple[tuple[str, str], ...] = ()  # (param, value as source text)
    help: str = ""  # flag help text
    body: str = ""  # structure of a function body, ignoring formatting


@dataclass(frozen=True)
class Change:
    """One difference between the old and new facts of a file."""

    kind: str  # one of the change kinds above
    symbol: str  # the old name, as docs would mention it
    old: str  # human-readable "before"
    new: str  # human-readable "after"
    old_line: int | None
    new_line: int | None


def _is_public(name: str) -> bool:
    return not name.startswith("_")


def _function_fact(node: ast.FunctionDef | ast.AsyncFunctionDef, name: str) -> Fact:
    args = node.args
    positional = [a.arg for a in args.posonlyargs + args.args]
    keyword_only = [a.arg for a in args.kwonlyargs]
    params = tuple(p for p in positional + keyword_only if p not in ("self", "cls"))

    defaults: list[tuple[str, str]] = []
    # Positional defaults belong to the LAST len(args.defaults) positional params.
    for param, value in zip(positional[len(positional) - len(args.defaults):], args.defaults):
        defaults.append((param, ast.unparse(value)))
    for param, value in zip(keyword_only, args.kw_defaults):
        if value is not None:  # None here means "keyword-only with no default"
            defaults.append((param, ast.unparse(value)))

    statements = node.body
    if statements and isinstance(statements[0], ast.Expr) and isinstance(
        statements[0].value, ast.Constant
    ) and isinstance(statements[0].value.value, str):
        statements = statements[1:]  # skip the docstring: that is docs, not code
    body = "\n".join(ast.dump(s) for s in statements)

    return Fact("function", name, node.lineno, params, tuple(defaults), body=body)


def _flag_fact(call: ast.Call) -> Fact | None:
    names = [
        a.value for a in call.args
        if isinstance(a, ast.Constant) and isinstance(a.value, str) and a.value.startswith("-")
    ]
    if not names:
        return None
    name = max(names, key=len)  # prefer "--verbose" over "-v"
    keywords = {k.arg: k.value for k in call.keywords if k.arg is not None}
    default = ast.unparse(keywords["default"]) if "default" in keywords else ""
    help_node = keywords.get("help")
    help_text = help_node.value if isinstance(help_node, ast.Constant) else ""
    return Fact(
        "flag", name, call.lineno,
        defaults=(("default", default),) if default else (),
        help=str(help_text),
    )


def extract_facts(source: str) -> dict[str, Fact] | None:
    """All public facts in a Python file, by name. None if the file can't be parsed."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    facts: dict[str, Fact] = {}

    for node in tree.body:  # top level only, for functions/classes/constants
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_public(node.name):
            facts[node.name] = _function_fact(node, node.name)
        elif isinstance(node, ast.ClassDef) and _is_public(node.name):
            facts[node.name] = Fact("class", node.name, node.lineno)
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_public(item.name):
                    full = f"{node.name}.{item.name}"
                    facts[full] = _function_fact(item, full)
        elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            for target in node.targets:
                if isinstance(target, ast.Name) and _is_public(target.id):
                    facts[target.id] = Fact(
                        "constant", target.id, node.lineno,
                        defaults=(("value", ast.unparse(node.value)),),
                    )
        elif isinstance(node, ast.AnnAssign) and isinstance(node.value, ast.Constant):
            if isinstance(node.target, ast.Name) and _is_public(node.target.id):
                facts[node.target.id] = Fact(
                    "constant", node.target.id, node.lineno,
                    defaults=(("value", ast.unparse(node.value)),),
                )

    for node in ast.walk(tree):  # flags can be defined anywhere
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in FLAG_METHODS
        ):
            fact = _flag_fact(node)
            if fact is not None:
                facts[fact.name] = fact

    return facts


def _same_shape(a: Fact, b: Fact) -> bool:
    """Could b be a, renamed? Same kind, same parameters, defaults, help and body."""
    return (a.kind, a.params, a.defaults, a.help, a.body) == (b.kind, b.params, b.defaults, b.help, b.body)


def compare_facts(old: dict[str, Fact], new: dict[str, Fact]) -> list[Change]:
    """Changes that could make documentation of the OLD code wrong."""
    changes: list[Change] = []
    removed = [old[n] for n in old if n not in new]
    added = [new[n] for n in new if n not in old]

    not_renamed = []
    for gone in removed:
        twins = [a for a in added if _same_shape(gone, a)]
        if len(twins) == 1:  # exactly one look-alike: a rename
            twin = twins[0]
            added.remove(twin)
            changes.append(Change(RENAMED, gone.name, gone.name, twin.name, gone.line, twin.line))
        else:
            not_renamed.append(gone)

    for gone in not_renamed:
        # Not a clean rename. New names of the same kind in this file are
        # possible replacements; the report shows them as a hint.
        candidates = ", ".join(a.name for a in added if a.kind == gone.kind)
        changes.append(Change(REMOVED, gone.name, gone.name, candidates, gone.line, None))

    for name in old:
        if name not in new:
            continue
        before, after = old[name], new[name]
        if before.params != after.params:
            changes.append(Change(
                SIGNATURE_CHANGED, name,
                f"{name}({', '.join(before.params)})", f"{name}({', '.join(after.params)})",
                before.line, after.line,
            ))
            continue
        old_defaults, new_defaults = dict(before.defaults), dict(after.defaults)
        changed_defaults = [p for p in old_defaults if old_defaults[p] != new_defaults.get(p)]
        for param in changed_defaults:
            changes.append(Change(
                DEFAULT_CHANGED, name,
                f"{param}={old_defaults[param]}", f"{param}={new_defaults.get(param, '(none)')}",
                before.line, after.line,
            ))
        if not changed_defaults and (before.help != after.help or before.body != after.body):
            changes.append(Change(
                HELP_OR_BODY_CHANGED, name, before.help, after.help, before.line, after.line,
            ))

    # Symbols that only exist in the new code are new features: docs written
    # for the old code can't be wrong about them, so they are not reported.
    return changes
