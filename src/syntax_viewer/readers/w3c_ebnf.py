"""W3C EBNF reader (FR-3): the notation of the XML specification.

    symbol ::= expression        (no terminator; the next `name ::=` ends it)

`[a-z]` / `[^abc]` are character classes (not optional), `#xN` is a
character code, `/* */` are comments. Optional XML-spec rule numbers
(`[12]`) are skipped; `[ WFC: ... ]` / `[ VC: ... ]` notes are kept as
comments so they attach to the rule (FR-15).
"""

from __future__ import annotations

import re

from syntax_viewer.model import (
    Comment,
    Except,
    Expr,
    Grammar,
    Literal,
    Opt,
    Plus,
    Regex,
    Rule,
    Star,
    SymRef,
    alt,
    attach_comments,
    seq,
)
from syntax_viewer.readers import Reader, register
from syntax_viewer.readers.iso_ebnf import strip_comments
from syntax_viewer.readers.tokens import Tok, TokenParser

_TOKEN = re.compile(
    r"""
    (?P<ws>\s+)
  | (?P<comment>/\*.*?\*/|\[\s*(?:WFC|VC|wfc|vc)\s*:[^\]]*\])
  | (?P<number>\[[0-9]+\])
  | (?P<string>"[^"]*"|'[^']*')
  | (?P<charclass>\[(?:\\.|[^\]\\])+\])
  | (?P<charcode>\#x[0-9A-Fa-f]+)
  | (?P<name>[A-Za-z_](?:[A-Za-z0-9_.-]|:(?!:=))*)
  | (?P<punct>::=|[|()?*+-])
    """,
    re.X | re.S,
)
_RULE = re.compile(r"^[ \t]*(?:\[[0-9]+\][ \t]*)?[A-Za-z_][\w.:-]*[ \t]*::=", re.M)


class _Parser(TokenParser):
    def __init__(self, text: str, path: str | None):
        super().__init__(text, path)
        self.comments: list[Comment] = []
        pos = 0
        while pos < len(text):
            m = _TOKEN.match(text, pos)
            if not m:
                if text.startswith("/*", pos):
                    raise self.error("unterminated comment", pos)
                raise self.error(f"unexpected character {text[pos]!r}", pos)
            kind = m.lastgroup
            if kind == "comment":
                self.comments.append(Comment(m.group(), self.span(pos, m.end())))
            elif kind not in ("ws", "number"):
                self.toks.append(Tok(kind, m.group(), pos, m.end()))
            pos = m.end()
        self.toks.append(Tok("eof", "", len(text), len(text)))

    def at_rule_start(self) -> bool:
        nxt = self.peek()
        return self.tok.kind == "name" and nxt.kind == "punct" and nxt.text == "::="

    def grammar(self, g: Grammar) -> None:
        while self.tok.kind != "eof":
            if not self.at_rule_start():
                raise self.error(f"expected 'name ::=', found {self.tok.text!r}", self.tok.start)
            head = self.take()
            self.take()
            body = self.choice()
            if self.tok.kind != "eof" and not self.at_rule_start():
                raise self.error(f"unexpected {self.tok.text!r}", self.tok.start)
            last = self.toks[self.i - 1]
            g.add_rule(Rule(head.text, body, self.span(head.start, last.end)))

    def choice(self) -> Expr:
        opts = [self.sequence()]
        while self.at("|"):
            self.take()
            opts.append(self.sequence())
        return alt(*opts)

    def sequence(self) -> Expr:
        items: list[Expr] = []
        while self.tok.kind in ("name", "string", "charclass", "charcode") or self.at("("):
            if self.at_rule_start():
                break
            items.append(self.term())
        return seq(*items)

    def term(self) -> Expr:
        base = self.postfix()
        if self.at("-"):
            self.take()
            return Except(base, self.postfix())
        return base

    def postfix(self) -> Expr:
        expr = self.primary()
        while self.at("?", "*", "+"):
            op = self.take().text
            expr = {"?": Opt, "*": Star, "+": Plus}[op](expr)
        return expr

    def primary(self) -> Expr:
        tok = self.take()
        if tok.kind == "name":
            return SymRef(tok.text)
        if tok.kind in ("string", "charcode"):
            return Literal(tok.text)
        if tok.kind == "charclass":
            return Regex(tok.text)
        if tok.text == "(":
            inner = self.choice()
            self.expect(")")
            return inner
        raise self.error(f"unexpected {tok.text or 'end of file'!r}", tok.start)


class W3cEbnfReader(Reader):
    name = "ebnf-w3c"
    extensions = (".ebnf", ".w3c")

    def detect(self, path, text):
        score = super().detect(path, text)
        if not score:
            return 0.0
        body = re.sub(r"/\*.*?\*/", "", strip_comments(text), flags=re.S)
        return score + (0.4 if _RULE.search(body) else 0.0)

    def read(self, text, path=None):
        g = Grammar(format=self.name, source=text, path=path)
        parser = _Parser(text, path)
        parser.grammar(g)
        attach_comments(text, [r for rules in g.rules.values() for r in rules], parser.comments)
        return g.finalize()


register(W3cEbnfReader())
