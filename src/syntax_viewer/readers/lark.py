"""Lark grammar reader (FR-3).

Hand-written rather than using the `lark` package's loader, which drops the
comments and source positions needed by FR-11 and FR-15. Terminal
definitions (`NAME: ...`) are stored as rules marked lexical, so they get
spans, comments and used-by like any rule while being listed as terminals.
"""

from __future__ import annotations

import re

from syntax_viewer.model import (
    Call,
    Comment,
    Empty,
    Expr,
    Grammar,
    Kind,
    Literal,
    Opt,
    Param,
    Plus,
    Range,
    Regex,
    Repeat,
    Rule,
    SourceSpan,
    Star,
    Symbol,
    SymRef,
    alt,
    attach_comments,
    seq,
)
from syntax_viewer.readers import Reader, register
from syntax_viewer.readers.tokens import Tok, TokenParser

_TOKEN = re.compile(
    r"""
    (?P<nl>\r?\n)
  | (?P<ws>[ \t\f\r]+)
  | (?P<comment>//[^\n]*)
  | (?P<directive>%[a-z]+)
  | (?P<string>"(?:\\.|[^"\\\n])*"i?)
  | (?P<regex>/(?!/)(?:\\.|[^/\\\n])+/[imslux]*)
  | (?P<name>_?[A-Za-z][A-Za-z0-9_]*)
  | (?P<int>[0-9]+)
  | (?P<punct>->|\.\.|[:|()\[\]?!*+~.,{}=])
    """,
    re.X,
)
_RULE_LINE = re.compile(r"^[ \t]*[?!]?_?[a-z][a-z0-9_]*(?:\.-?[0-9]+)?[ \t]*:", re.M)


def _is_terminal(name: str) -> bool:
    return name.lstrip("_")[:1].isupper()


class _Parser(TokenParser):
    def __init__(self, text: str, path: str | None):
        super().__init__(text, path)
        self.params: tuple[str, ...] = ()  # parameters of the template being parsed
        self.comments: list[Comment] = []
        self.toks = self._tokenize()

    def _tokenize(self) -> list[Tok]:
        toks: list[Tok] = []
        pos, n = 0, len(self.text)
        while pos < n:
            m = _TOKEN.match(self.text, pos)
            if not m:
                raise self.error(f"unexpected character {self.text[pos]!r}", pos)
            kind = m.lastgroup
            if kind == "comment":
                self._add_comment(pos, m.end())
            elif kind != "ws":
                toks.append(Tok(kind, m.group(), pos, m.end()))
            pos = m.end()
        toks.append(Tok("eof", "", n, n))
        return toks

    def _add_comment(self, start: int, end: int) -> None:
        """Record a `//` comment, merging it with the previous one when only
        a line break and indentation separate them (one block per FR-15)."""
        if self.comments:
            prev = self.comments[-1]
            gap = self.text[prev.span.end : start]
            if gap.strip() == "" and gap.count("\n") == 1:
                self.comments[-1] = Comment(self.text[prev.span.start : end], SourceSpan(prev.span.start, end, prev.span.line))
                return
        self.comments.append(Comment(self.text[start:end], self.span(start, end)))

    # -- token helpers --

    def skip_nl(self) -> None:
        while self.tok.kind == "nl":
            self.i += 1

    def continues_with_bar(self) -> bool:
        """At a newline: does the statement continue on a later `|` line?"""
        j = self.i
        while self.toks[j].kind == "nl":
            j += 1
        if self.toks[j].kind == "punct" and self.toks[j].text == "|":
            self.i = j
            return True
        return False

    def end_of_statement(self) -> None:
        if self.tok.kind not in ("nl", "eof"):
            raise self.error(f"unexpected {self.tok.text!r}", self.tok.start)

    # -- statements --

    def grammar(self, g: Grammar) -> None:
        self.skip_nl()
        while self.tok.kind != "eof":
            if self.tok.kind == "directive":
                self.directive(g)
            elif self.tok.kind == "name" or (self.at("?", "!") and self.peek().kind == "name"):
                self.definition(g)
            else:
                raise self.error(f"expected rule, terminal or directive, found {self.tok.text!r}", self.tok.start)
            self.skip_nl()

    def definition(self, g: Grammar) -> None:
        head = self.take()
        if head.kind == "punct":  # `?rule` / `!rule` prefix
            name = self.take().text
        else:
            name = head.text
        params: tuple[str, ...] = ()
        if self.at("{"):
            params = self.template_params()
        priority = None
        if self.at(".") and self.peek().kind == "int":
            self.take()
            priority = self.take().text
        self.expect(":")
        self.params = params
        body = self.expansions()
        self.params = ()
        last = self.toks[self.i - 1]
        self.end_of_statement()
        g.add_rule(Rule(name, body, self.span(head.start, last.end), params=params))
        if _is_terminal(name):
            g.lexical.add(name)
            if priority:
                self._annotate(g, name, f"priority {priority}")

    def directive(self, g: Grammar) -> None:
        tok = self.take()
        if tok.text in ("%override", "%extend"):
            target = self.peek(1 if self.at("?", "!") else 0)
            if target.kind != "name":
                raise self.error(f"expected rule after {tok.text}", self.tok.start)
            if tok.text == "%override":
                g.rules.pop(target.text, None)
            self.definition(g)
            return
        args: list[Tok] = []
        while self.tok.kind not in ("nl", "eof"):
            args.append(self.take())
        if tok.text == "%import":
            self._import(g, tok, args)
        elif tok.text == "%declare":
            for a in args:
                if a.kind == "name":
                    kind = Kind.TERMINAL if _is_terminal(a.text) else Kind.NONTERMINAL
                    self._declare(g, a.text, kind, "%declare", a)
        elif tok.text == "%ignore":
            if len(args) == 1 and args[0].kind == "name":
                self._annotate(g, args[0].text, "%ignore")
        else:
            raise self.error(f"unknown directive {tok.text}", tok.start)

    def _import(self, g: Grammar, tok: Tok, args: list[Tok]) -> None:
        text = self.text[tok.start : args[-1].end] if args else tok.text
        texts = [a.text for a in args]
        if "(" in texts:
            names = [a for a in args[texts.index("(") + 1 :] if a.kind == "name"]
        elif "->" in texts:
            names = [args[texts.index("->") + 1]]
        else:
            names = [a for a in args if a.kind == "name"][-1:]
        if not names:
            raise self.error("expected name in %import", tok.start)
        for a in names:
            kind = Kind.TERMINAL if _is_terminal(a.text) else Kind.NONTERMINAL
            self._declare(g, a.text, kind, text, a)

    def _declare(self, g: Grammar, name: str, kind: Kind, declaration: str, tok: Tok) -> None:
        span = self.span(tok.start, tok.end)
        if kind is Kind.TERMINAL:
            g.declare_terminal(name, declaration=declaration, span=span)
        else:
            g.symbols.setdefault(name, Symbol(name, kind, declaration=declaration, span=span))

    def _annotate(self, g: Grammar, name: str, note: str) -> None:
        sym = g.symbols.get(name)
        if sym is None:
            g.declare_terminal(name, declaration=note)
        else:
            sym.declaration = f"{sym.declaration}; {note}" if sym.declaration else note

    # -- expressions --

    def expansions(self) -> Expr:
        opts = [self.alias()]
        while self.at("|") or (self.tok.kind == "nl" and self.continues_with_bar()):
            self.take()
            self.skip_nl()
            opts.append(self.alias())
        return alt(*opts)

    def alias(self) -> Expr:
        items: list[Expr] = []
        while self.tok.kind in ("name", "string", "regex") or self.at("(", "["):
            items.append(self.expr())
        if self.at("->"):
            self.take()
            if self.tok.kind != "name":
                raise self.error("expected alias name after '->'", self.tok.start)
            self.take()
        return seq(*items) if items else Empty()

    def expr(self) -> Expr:
        atom = self.atom()
        if self.at("?"):
            self.take()
            return Opt(atom)
        if self.at("*"):
            self.take()
            return Star(atom)
        if self.at("+"):
            self.take()
            return Plus(atom)
        if self.at("~"):
            self.take()
            low = self.take()
            if low.kind != "int":
                raise self.error("expected number after '~'", low.start)
            high = None
            if self.at(".."):
                self.take()
                high = self.take().text
            return Repeat(int(low.text), atom, int(high) if high else None)
        return atom

    def template_params(self) -> tuple[str, ...]:
        """`{a, b}` after a template's name."""
        self.expect("{")
        names = []
        while True:
            if self.tok.kind != "name":
                raise self.error(f"expected template parameter, found {self.describe(self.tok)!r}", self.tok.start)
            names.append(self.take().text)
            if self.expect(",", "}").text == "}":
                return tuple(names)

    def template_args(self) -> tuple[Expr, ...]:
        """`{X, ","}` after a template's name in a rule body."""
        self.expect("{")
        args = [self.expr()]
        while self.expect(",", "}").text == ",":
            args.append(self.expr())
        return tuple(args)

    def atom(self) -> Expr:
        tok = self.take()
        if tok.kind == "name":
            if tok.text in self.params:
                return Param(tok.text)
            if self.at("{"):
                return Call(tok.text, self.template_args())
            return SymRef(tok.text)
        if tok.kind == "regex":
            return Regex(tok.text)
        if tok.kind == "string":
            if self.at(".."):
                self.take()
                high = self.take()
                if high.kind != "string":
                    raise self.error("expected string after '..'", high.start)
                return Range(tok.text, high.text)
            return Literal(tok.text)
        if tok.text == "(":
            self.skip_nl()
            inner = self.expansions()
            self.skip_nl()
            self.expect(")")
            return inner
        if tok.text == "[":
            self.skip_nl()
            inner = self.expansions()
            self.skip_nl()
            self.expect("]")
            return Opt(inner)
        raise self.error(f"unexpected {tok.text or 'end of file'!r}", tok.start)


class LarkReader(Reader):
    name = "lark"
    extensions = (".lark",)

    def detect(self, path, text):
        score = super().detect(path, text)
        return score + (0.4 if score and _RULE_LINE.search(text) else 0.0)

    def read(self, text, path=None):
        g = Grammar(format=self.name, source=text, path=path, native_terminals=True)
        parser = _Parser(text, path)
        parser.grammar(g)
        rules = [r for name in g.rules for r in g.rules[name]]
        g.start = "start" if "start" in g.rules else next((n for n in g.rules if n not in g.lexical), None)
        attach_comments(text, rules, parser.comments)
        return g.finalize()


register(LarkReader())
