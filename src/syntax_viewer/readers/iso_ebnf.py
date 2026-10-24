"""ISO/IEC 14977 EBNF reader (FR-3), tolerant of common informal variants:

- concatenation by `,` or by plain juxtaposition
- hyphenated names (`name-start`)
- informal character ranges `"a" .. "z"`
- nested `(* *)` comments, attached to rules (FR-15)
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
    Range,
    Repeat,
    Rule,
    Special,
    Star,
    SymRef,
    alt,
    attach_comments,
    seq,
)
from syntax_viewer.readers import Reader, register
from syntax_viewer.readers.tokens import Tok, TokenParser

_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]*(?:-[A-Za-z0-9_]+)*")
_INT = re.compile(r"[0-9]+")
_PUNCT = ("..", "(/", "/)", "(:", ":)", "=", ";", ".", "|", "/", "!", ",", "-", "*",
          "[", "]", "{", "}", "(", ")")
_RULE_START = re.compile(r"^[ \t]*[A-Za-z][\w-]*[ \t]*=(?!=)", re.M)
_W3C_RULE = re.compile(r"^[ \t]*[A-Za-z][\w.-]*[ \t]*::=", re.M)


def strip_comments(text: str) -> str:
    """Remove nested `(* *)` comments (used for format sniffing)."""
    out, depth, i = [], 0, 0
    while i < len(text):
        if text.startswith("(*", i):
            depth, i = depth + 1, i + 2
        elif depth and text.startswith("*)", i):
            depth, i = depth - 1, i + 2
        else:
            if not depth:
                out.append(text[i])
            i += 1
    return "".join(out)


class _Parser(TokenParser):
    def __init__(self, text: str, path: str | None):
        super().__init__(text, path)
        self.comments: list[Comment] = []
        self.toks = self._tokenize()

    # -- lexing (tokens: name, string, special, int, punct, eof) --

    def _tokenize(self) -> list[Tok]:
        text, n, i = self.text, len(self.text), 0
        toks: list[Tok] = []
        while i < n:
            ch = text[i]
            if ch.isspace():
                i += 1
            elif text.startswith("(*", i):
                i = self._comment(i)
            elif ch in "\"'":
                j = text.find(ch, i + 1)
                if j < 0:
                    raise self.error("unterminated string", i)
                toks.append(Tok("string", text[i : j + 1], i, j + 1))
                i = j + 1
            elif ch == "?":
                j = text.find("?", i + 1)
                if j < 0:
                    raise self.error("unterminated special sequence", i)
                toks.append(Tok("special", text[i : j + 1], i, j + 1))
                i = j + 1
            elif m := _NAME.match(text, i):
                toks.append(Tok("name", m.group(), i, m.end()))
                i = m.end()
            elif m := _INT.match(text, i):
                toks.append(Tok("int", m.group(), i, m.end()))
                i = m.end()
            else:
                for p in _PUNCT:
                    if text.startswith(p, i):
                        toks.append(Tok("punct", p, i, i + len(p)))
                        i += len(p)
                        break
                else:
                    raise self.error(f"unexpected character {ch!r}", i)
        toks.append(Tok("eof", "", n, n))
        return toks

    def _comment(self, start: int) -> int:
        depth, i = 0, start
        while i < len(self.text):
            if self.text.startswith("(*", i):
                depth, i = depth + 1, i + 2
            elif self.text.startswith("*)", i):
                depth, i = depth - 1, i + 2
                if depth == 0:
                    self.comments.append(Comment(self.text[start:i], self.span(start, i)))
                    return i
            else:
                i += 1
        raise self.error("unterminated comment", start)

    # -- parsing --

    def grammar(self, g: Grammar) -> None:
        while self.tok.kind != "eof":
            start = self.tok
            if start.kind != "name":
                raise self.error(f"expected rule name, found {start.text!r}", start.start)
            self.take()
            self.expect("=")
            body = self.definitions()
            end = self.expect(";", ".")
            g.add_rule(Rule(start.text, body, self.span(start.start, end.end)))

    def definitions(self) -> Expr:
        opts = [self.single()]
        while self.at("|", "/", "!"):
            self.take()
            opts.append(self.single())
        return alt(*opts)

    def _starts_primary(self) -> bool:
        tok = self.tok
        if tok.kind == "name":
            # `x =` starts the next rule: the current one lacks its `;`.
            nxt = self.peek()
            if nxt.kind == "punct" and nxt.text == "=":
                raise self.error("missing ';' before next rule", tok.start)
            return True
        if tok.kind in ("string", "special", "int"):
            return True
        return self.at("[", "{", "(", "(/", "(:")

    def single(self) -> Expr:
        items: list[Expr] = []
        while True:
            if self.at(","):
                self.take()
            if not self._starts_primary():
                break
            items.append(self.term())
        return seq(*items)

    def term(self) -> Expr:
        base = self.factor()
        if self.at("-"):
            self.take()
            return Except(base, self.factor())
        return base

    def factor(self) -> Expr:
        if self.tok.kind == "int" and self.peek().text == "*":
            count = int(self.take().text)
            self.take()
            return Repeat(count, self.primary())
        return self.primary()

    def primary(self) -> Expr:
        tok = self.take()
        if tok.kind == "name":
            return SymRef(tok.text)
        if tok.kind == "special":
            return Special(tok.text)
        if tok.kind == "string":
            if self.at(".."):
                self.take()
                high = self.take()
                if high.kind != "string":
                    raise self.error("expected string after '..'", high.start)
                return Range(tok.text, high.text)
            return Literal(tok.text)
        if tok.kind == "punct":
            close = {"[": "]", "(/": "/)", "{": "}", "(:": ":)", "(": ")"}.get(tok.text)
            if close:
                inner = self.definitions()
                self.expect(close)
                if close in ("]", "/)"):
                    return Opt(inner)
                if close in ("}", ":)"):
                    return Star(inner)
                return inner
        raise self.error(f"unexpected {tok.text or 'end of file'!r}", tok.start)


class IsoEbnfReader(Reader):
    name = "ebnf-iso"
    extensions = (".ebnf", ".iso")

    def detect(self, path, text):
        score = super().detect(path, text)
        if not score:
            return 0.0
        body = strip_comments(text)
        if _W3C_RULE.search(body):
            return 0.1
        return score + (0.4 if _RULE_START.search(body) else 0.0)

    def read(self, text, path=None):
        g = Grammar(format=self.name, source=text, path=path)
        parser = _Parser(text, path)
        parser.grammar(g)
        attach_comments(text, [r for rules in g.rules.values() for r in rules], parser.comments)
        return g.finalize()


register(IsoEbnfReader())
