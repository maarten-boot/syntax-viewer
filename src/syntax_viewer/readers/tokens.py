"""Building blocks shared by all readers: tokens, source positions and a
bounded token cursor (look-ahead never runs past the final eof token)."""

from __future__ import annotations

import bisect
import re
from dataclasses import dataclass

from syntax_viewer.model import GrammarError, SourceSpan


@dataclass
class Tok:
    kind: str  # reader-specific: name, string, punct, ..., always ending with eof
    text: str
    start: int
    end: int


class Source:
    """Line lookup and positioned errors for one input text (NFR-2)."""

    def __init__(self, text: str, path: str | None):
        self.text = text
        self.path = path
        self._lines = [0] + [m.end() for m in re.finditer(r"\n", text)]

    def line(self, offset: int) -> int:
        return bisect.bisect_right(self._lines, offset)

    def span(self, start: int, end: int) -> SourceSpan:
        return SourceSpan(start, end, self.line(start))

    def error(self, msg: str, offset: int) -> GrammarError:
        return GrammarError(msg, self.path, self.line(offset))


class TokenParser(Source):
    """Cursor over `self.toks`, which subclasses fill (last token: eof)."""

    def __init__(self, text: str, path: str | None):
        super().__init__(text, path)
        self.toks: list[Tok] = []
        self.i = 0

    @property
    def tok(self) -> Tok:
        return self.peek(0)

    def peek(self, k: int = 1) -> Tok:
        """Token `k` ahead; never past the final eof token."""
        return self.toks[min(self.i + k, len(self.toks) - 1)]

    def take(self) -> Tok:
        tok = self.tok
        self.i = min(self.i + 1, len(self.toks))
        return tok

    def at(self, *punct: str) -> bool:
        return self.tok.kind == "punct" and self.tok.text in punct

    def at_kind(self, kind: str, *texts: str) -> bool:
        return self.tok.kind == kind and (not texts or self.tok.text in texts)

    @staticmethod
    def describe(tok: Tok) -> str:
        return {"eof": "end of file", "nl": "end of line"}.get(tok.kind, tok.text)

    def expect(self, *punct: str) -> Tok:
        if not self.at(*punct):
            wanted = " or ".join(map(repr, punct))
            raise self.error(f"expected {wanted}, found {self.describe(self.tok)!r}", self.tok.start)
        return self.take()
