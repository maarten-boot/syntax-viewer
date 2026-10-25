"""Normalised (format-independent) rendering of rules (FR-11a)."""

from __future__ import annotations

from typing import Callable

from syntax_viewer.model import (
    Alt,
    Call,
    Empty,
    Except,
    Expr,
    Grammar,
    Opt,
    Param,
    Plus,
    Repeat,
    Seq,
    Star,
    alternatives,
    symbol_name,
)

# Formats a leaf symbol's text (e.g. as an HTML link); identity for plain text.
Leaf = Callable[[str], str]


def _plain(text: str) -> str:
    return text

# Binding strength, used to decide where parentheses are needed.
_PREC = {Alt: 0, Seq: 1, Except: 2, Repeat: 2, Opt: 3, Star: 3, Plus: 3}


def _prec(expr: Expr) -> int:
    return _PREC.get(type(expr), 4)  # leaves bind tightest


def expr_text(expr: Expr, outer: int = 0, leaf: Leaf = _plain) -> str:
    if isinstance(expr, Call):
        return f"{leaf(expr.name)}{{{', '.join(expr_text(a, 0, leaf) for a in expr.args)}}}"
    if isinstance(expr, Param):
        return expr.name
    name = symbol_name(expr)
    if name is not None:
        text = leaf(name)
    elif isinstance(expr, Empty):
        text = "ε"
    elif isinstance(expr, Except):
        text = f"{expr_text(expr.base, 3, leaf)} - {expr_text(expr.exclude, 3, leaf)}"
    elif isinstance(expr, Repeat):
        count = f"{expr.count}..{expr.high}" if expr.high is not None else str(expr.count)
        text = f"{count} * {expr_text(expr.expr, 3, leaf)}"
    elif isinstance(expr, Seq):
        text = " ".join(expr_text(i, 2, leaf) for i in expr.items)
    elif isinstance(expr, Alt):
        text = " | ".join(expr_text(o, 1, leaf) for o in expr.options)
    elif isinstance(expr, (Opt, Star, Plus)):
        op = {Opt: "?", Star: "*", Plus: "+"}[type(expr)]
        return expr_text(expr.expr, 3, leaf) + op
    else:  # pragma: no cover - new node type without renderer
        raise TypeError(f"cannot render {expr!r}")
    return f"( {text} )" if _prec(expr) < outer else text


def rule_text(grammar: Grammar, name: str, leaf: Leaf = _plain) -> str:
    """`name ::= alt1\\n    | alt2 ...` with one alternative per line."""
    body = grammar.body(name)
    if body is None:
        return ""
    alts = [expr_text(a, 1, leaf) for a in alternatives(body)]
    params = grammar.rules[name][0].params
    head = f"{name}{{{', '.join(params)}}}" if params else name
    pad = " " * len(head)
    lines = [f"{leaf(name)}{head[len(name):]} ::= {alts[0]}"] + [f"{pad}   | {a}" for a in alts[1:]]
    return "\n".join(lines)
