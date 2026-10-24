"""Lemon reader (FR-3): rule structure only.

Rules are `lhs(A) ::= rhs(B) X|Y . [PREC] { action }`; aliases, `[PREC]`
and actions are dropped (actions follow the rule's span, so the original
view needs no elision). Names starting with an upper-case letter are
terminals. `%token`, `%left`/`%right`/`%nonassoc`, `%fallback`,
`%wildcard`, `%token_class`, `%type` and `%start_symbol` are used;
`%ifdef`/`%ifndef`/`%if`/`%else`/`%endif` lines are ignored, so every rule
is shown; every other directive's single argument is skipped.
"""

from __future__ import annotations

import re

from syntax_viewer.model import (
    Expr,
    Grammar,
    Kind,
    Rule,
    SourceSpan,
    Symbol,
    SymRef,
    alt,
    attach_comments,
    seq,
)
from syntax_viewer.readers import Reader, register
from syntax_viewer.readers.clex import CLexer
from syntax_viewer.readers.tokens import Tok, TokenParser

_CONDITIONALS = frozenset({"%ifdef", "%ifndef", "%if", "%else", "%elsif", "%endif"})  # skipped by the lexer
_LISTS = {"%token", "%left", "%right", "%nonassoc", "%fallback", "%wildcard", "%token_class"}
_SECTIONS = re.compile(r"^%%", re.M)
_RULE = re.compile(r"^[ \t]*[a-z_]\w*[ \t]*(?:\([ \t]*\w+[ \t]*\))?[ \t]*::=", re.M)


def _is_terminal(name: str) -> bool:
    return name[:1].isupper()


class _Parser(TokenParser):
    def __init__(self, text: str, path: str | None):
        super().__init__(text, path)
        self.lx = CLexer(text, path, r"[A-Za-z_]\w*", ("::=", ".", "(", ")", "[", "]", "|"), _CONDITIONALS)
        self.toks = self.lx.tokens()

    def grammar(self, g: Grammar) -> None:
        while self.tok.kind != "eof":
            if self.tok.kind == "directive":
                self.directive(g)
            elif self.tok.kind == "name":
                self.rule(g)
            else:
                raise self.error(f"expected rule or directive, found {self.tok.text!r}", self.tok.start)

    # -- directives --

    def directive(self, g: Grammar) -> None:
        tok = self.take()
        if tok.text in _LISTS:
            names: list[Tok] = []
            while not self.at("."):
                if self.tok.kind in ("eof", "directive") or self.at("::="):
                    started = self.line(tok.start)
                    raise self.error(f"expected '.' to end {tok.text} (started on line {started})", self.tok.start)
                t = self.take()
                if t.kind == "name":
                    names.append(t)
            self.take()
            self.symbol_list(g, tok, names)
        elif tok.text in ("%type", "%destructor") and self.at_kind("name"):
            name = self.take()
            arg = self.take() if self.at_kind("block") else None
            if tok.text == "%type":
                decl = f"%type {arg.text}" if arg else "%type"
                kind = Kind.TERMINAL if _is_terminal(name.text) else Kind.NONTERMINAL
                sym = g.symbols.setdefault(name.text, Symbol(name.text, kind))
                sym.declaration = decl
        elif tok.text == "%start_symbol" and self.at_kind("name"):
            g.start = self.take().text
        elif self.tok.kind != "directive" and self.tok.kind != "eof":
            self.take()  # the directive's single argument

    def symbol_list(self, g: Grammar, tok: Tok, names: list[Tok]) -> None:
        directive = tok.text
        if directive == "%token_class" and names:
            first, *members = names
            body = alt(*(SymRef(m.text) for m in members)) if members else None
            text = self.text[tok.start : self.toks[self.i - 1].end]
            g.declare_terminal(first.text, definition=body, declaration=text, span=self._span(first))
            return
        if directive == "%fallback" and names:
            target, *names = names
            self._declare(g, target, "%fallback target")
            for n in names:
                self._declare(g, n, f"%fallback → {target.text}")
            return
        for n in names:
            self._declare(g, n, directive)

    def _span(self, tok: Tok) -> SourceSpan:
        return self.span(tok.start, tok.end)

    def _declare(self, g: Grammar, tok: Tok, note: str) -> None:
        sym = g.symbols.get(tok.text)
        if sym is None:
            g.declare_terminal(tok.text, declaration=note, span=self._span(tok))
        elif note not in (sym.declaration or ""):
            sym.declaration = f"{sym.declaration}; {note}" if sym.declaration else note

    # -- rules --

    def _alias(self) -> None:
        if self.at("("):
            self.take()
            if not self.at_kind("name"):
                raise self.error("expected alias name", self.tok.start)
            self.take()
            self.expect(")")

    def rule(self, g: Grammar) -> None:
        head = self.take()
        self._alias()
        self.expect("::=")
        items: list[Expr] = []
        while not self.at("."):
            if not self.at_kind("name"):
                found = self.tok.text or "end of file"
                raise self.error(f"expected symbol or '.', found {found!r}", self.tok.start)
            options = [SymRef(self.take().text)]
            while self.at("|"):  # multi-terminal X|Y
                self.take()
                options.append(SymRef(self.take().text))
            items.append(alt(*options))
            self._alias()
        end = self.take()
        if self.at("["):
            self.take(), self.take()
            self.expect("]")
        if self.at_kind("block"):
            self.take()
        g.add_rule(Rule(head.text, seq(*items), self.span(head.start, end.end)))


class LemonReader(Reader):
    name = "lemon"
    extensions = (".y", ".lemon")

    def detect(self, path, text):
        score = super().detect(path, text)
        if not score or _SECTIONS.search(text):  # `%%` means Yacc/Bison
            return score
        return score + (0.45 if _RULE.search(text) else 0.0)

    def read(self, text, path=None):
        g = Grammar(format=self.name, source=text, path=path, native_terminals=True)
        p = _Parser(text, path)
        p.grammar(g)
        start = g.start
        refs = {n.name for rs in g.rules.values() for r in rs for n in r.body.walk() if isinstance(n, SymRef)}
        for name in sorted(refs - set(g.symbols)):
            if _is_terminal(name):
                g.declare_terminal(name)
        g.start = start if start in g.rules else next(iter(g.rules), None)
        attach_comments(text, [r for rs in g.rules.values() for r in rs], p.lx.comments)
        return g.finalize()


register(LemonReader())
