"""Yacc/Bison reader (FR-3): rule structure only.

Declarations: `%token`/`%nterm`/`%type`/`%left`/`%right`/`%nonassoc`/
`%precedence` (with `<type>` tags, token numbers and string aliases) and
`%start` are used; every other directive and `%{ %}` is skipped. Rules:
`lhs [name]: rhs | rhs ;`, where actions, `%prec X`, `%empty`, `%dprec`,
`%merge`, `<type>` tags and `[name]` references are dropped from the
structure; actions are also elided from the original view (FR-11).
"""

from __future__ import annotations

import re

from syntax_viewer.model import (
    Expr,
    Grammar,
    Kind,
    Literal,
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

_SYMBOL_DECLS = {"%token", "%nterm", "%type", "%left", "%right", "%nonassoc", "%precedence"}
_PRECEDENCE = {"%left", "%right", "%nonassoc", "%precedence"}
_SECTIONS = re.compile(r"^%%", re.M)


class _Parser(TokenParser):
    def __init__(self, text: str, path: str | None):
        super().__init__(text, path)
        self.lx = CLexer(text, path, r"[A-Za-z_][\w.]*(?:-[\w.]+)*", (":", ";", "|", "<", ">", "[", "]", ",", "=", "-", "*"))
        self.toks = self.lx.tokens(sections=True)

    def skip_type_tag(self) -> str | None:
        """Skip `<type>` (may contain `*`, spaces, ...); return its text."""
        if not self.at("<"):
            return None
        start = self.take()
        while not self.at(">"):
            if self.tok.kind == "eof":
                raise self.error("unterminated '<type>'", start.start)
            self.take()
        end = self.take()
        return self.text[start.start : end.end]

    # -- declarations section --

    def declarations(self, g: Grammar) -> None:
        while not self.at_kind("directive", "%%"):
            tok = self.take()
            if tok.kind == "eof":
                raise self.error("missing '%%' before the rules", tok.start)
            if tok.kind != "directive":
                continue  # %{ %} blocks and arguments of skipped directives
            if tok.text in _SYMBOL_DECLS:
                self.symbol_decl(g, tok.text)
            elif tok.text == "%start" and self.at_kind("name"):
                g.start = self.take().text

    def symbol_decl(self, g: Grammar, directive: str) -> None:
        tag = None
        prev: Tok | None = None
        while self.tok.kind in ("name", "char", "string", "int", "punct") and not self.at(";"):
            if self.at("<"):
                tag = self.skip_type_tag()
                continue
            tok = self.take()
            if tok.kind == "string" and prev is not None and directive == "%token":
                g.declare_terminal(tok.text, declaration=f"alias of {prev.text}")
                self._annotate(g, prev.text, f"alias {tok.text}")
                continue
            if tok.kind not in ("name", "char"):
                continue
            prev = tok
            decl = f"{directive}{' ' + tag if tag else ''} {tok.text}"
            if directive in ("%nterm", "%type"):
                sym = g.symbols.setdefault(tok.text, Symbol(tok.text, Kind.NONTERMINAL))
                sym.declaration = f"{sym.declaration}; {decl}" if sym.declaration else decl
            elif directive in _PRECEDENCE and tok.text in g.symbols:
                self._annotate(g, tok.text, directive)
            else:
                span = self.span(tok.start, tok.end)
                g.declare_terminal(tok.text, declaration=decl if directive == "%token" else directive, span=span)

    def _annotate(self, g: Grammar, name: str, note: str) -> None:
        sym = g.symbols[name]
        sym.declaration = f"{sym.declaration}; {note}" if sym.declaration else note

    # -- rules section --

    def rules(self, g: Grammar) -> None:
        self.take()  # %%
        while self.tok.kind != "eof" and not self.at_kind("directive", "%%"):
            if self.at(";"):
                self.take()
                continue
            head = self.take()
            if head.kind != "name":
                raise self.error(f"expected rule name, found {head.text!r}", head.start)
            if self.at("["):
                self.take(), self.take(), self.take()  # [name]
            if not self.at(":"):
                raise self.error(f"expected ':' after {head.text!r}", self.tok.start)
            self.take()
            elided: list[SourceSpan] = []
            opts = [self.alternative(elided)]
            while self.at("|"):
                self.take()
                opts.append(self.alternative(elided))
            last = self.toks[self.i - 1]
            if self.at(";"):
                last = self.take()
            span = self.span(head.start, last.end)
            g.add_rule(Rule(head.text, alt(*opts), span, elided=elided))

    def _starts_rule(self) -> bool:
        if not self.at_kind("name"):
            return False
        nxt = self.peek(4 if self.peek().text == "[" else 1)
        return nxt.kind == "punct" and nxt.text == ":"

    def alternative(self, elided: list[SourceSpan]) -> Expr:
        items: list[Expr] = []
        while True:
            tok = self.tok
            if tok.kind == "eof" or self.at("|", ";") or self.at_kind("directive", "%%") or self._starts_rule():
                break
            if tok.kind == "name":
                items.append(SymRef(self.take().text))
            elif tok.kind in ("char", "string"):
                items.append(Literal(self.take().text))
            elif tok.kind == "block":
                self.take()
                elided.append(self.span(tok.start, tok.end))
            elif self.at_kind("directive", "%prec", "%dprec", "%merge", "%expect", "%expect-rr"):
                self.take()
                if not self.skip_type_tag():
                    self.take()
            elif self.at_kind("directive", "%empty"):
                self.take()
            elif self.at("<"):
                self.skip_type_tag()
            elif self.at("["):
                self.take(), self.take(), self.take()  # named reference [name]
            else:
                raise self.error(f"unexpected {tok.text!r} in rule", tok.start)
        return seq(*items)


class YaccReader(Reader):
    name = "yacc"
    extensions = (".y", ".yy", ".ypp", ".bison")

    def detect(self, path, text):
        score = super().detect(path, text)
        return score + (0.4 if score and _SECTIONS.search(text) else 0.0)

    def read(self, text, path=None):
        g = Grammar(format=self.name, source=text, path=path, native_terminals=True)
        p = _Parser(text, path)
        p.declarations(g)
        start = g.start
        p.rules(g)
        g.start = start or next(iter(g.rules), None)
        if any(isinstance(n, SymRef) and n.name == "error" for rs in g.rules.values() for r in rs for n in r.body.walk()):
            g.declare_terminal("error", declaration="predefined error token")
        attach_comments(text, [r for rs in g.rules.values() for r in rs], p.lx.comments)
        return g.finalize()


register(YaccReader())
