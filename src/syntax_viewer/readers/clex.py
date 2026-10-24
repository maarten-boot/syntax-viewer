"""Tokenizer shared by the Yacc/Bison and Lemon readers.

Both embed C code in `{ ... }` blocks; a block is returned as one `block`
token, skipped with awareness of nested braces, string and character
literals and comments. `/* */` and `//` comments become Comment objects.
"""

from __future__ import annotations

import re

from syntax_viewer.model import Comment
from syntax_viewer.readers.tokens import Source, Tok

# Token kinds: name, char, string, int, punct, directive, block, eof

_DIRECTIVE = re.compile(r"%(?:\{|\}|%|[A-Za-z_][\w-]*)")
_INT = re.compile(r"[0-9]+")
_C_SKIP = re.compile(r'"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'|/\*.*?\*/|//[^\n]*|[{}]', re.S)


class CLexer(Source):
    def __init__(
        self, text: str, path: str | None, name: str, punct: tuple[str, ...], line_directives: frozenset[str] = frozenset()
    ):
        super().__init__(text, path)
        # Directives whose whole line is skipped unparsed (Lemon `%ifdef X`, `%if !A && B`).
        self.line_directives = line_directives
        self._name = re.compile(name)
        self._punct = sorted(punct, key=len, reverse=True)
        self.comments: list[Comment] = []

    def skip_block(self, start: int) -> int:
        """`start` is at `{`; return the offset just past the matching `}`."""
        depth, pos = 0, start
        while True:
            m = _C_SKIP.search(self.text, pos)
            if m is None:
                raise self.error("unterminated '{' block", start)
            if m.group() == "{":
                depth += 1
            elif m.group() == "}":
                depth -= 1
                if depth == 0:
                    return m.end()
            pos = m.end()

    def comment_end(self, start: int) -> int:
        if self.text.startswith("//", start):
            end = self.text.find("\n", start)
            return len(self.text) if end < 0 else end
        end = self.text.find("*/", start + 2)
        if end < 0:
            raise self.error("unterminated comment", start)
        return end + 2

    def quoted_end(self, start: int) -> int:
        quote, pos = self.text[start], start + 1
        while pos < len(self.text) and self.text[pos] not in (quote, "\n"):
            pos += 2 if self.text[pos] == "\\" else 1
        if pos >= len(self.text) or self.text[pos] != quote:
            raise self.error("unterminated literal", start)
        return pos + 1

    def tokens(self, sections: bool = False) -> list[Tok]:
        """Tokenize the whole text. With `sections` (Yacc), `%{ ... %}` is one
        block token and tokenizing stops at the second `%%` (epilogue)."""
        text, pos, end = self.text, 0, len(self.text)
        toks: list[Tok] = []
        seen_sections = 0
        while pos < end:
            ch = text[pos]
            if ch.isspace():
                pos += 1
            elif text.startswith(("/*", "//"), pos):
                stop = self.comment_end(pos)
                self.comments.append(Comment(text[pos:stop], self.span(pos, stop)))
                pos = stop
            elif ch == "{":
                stop = self.skip_block(pos)
                toks.append(Tok("block", text[pos:stop], pos, stop))
                pos = stop
            elif ch in "'\"":
                stop = self.quoted_end(pos)
                toks.append(Tok("char" if ch == "'" else "string", text[pos:stop], pos, stop))
                pos = stop
            elif sections and text.startswith("%{", pos):
                stop = text.find("%}", pos)
                if stop < 0:
                    raise self.error("unterminated '%{' block", pos)
                toks.append(Tok("block", text[pos : stop + 2], pos, stop + 2))
                pos = stop + 2
            elif ch == "%" and (m := _DIRECTIVE.match(text, pos)):
                pos = m.end()
                if m.group() in self.line_directives:
                    eol = text.find("\n", pos)
                    pos = end if eol < 0 else eol
                    continue
                toks.append(Tok("directive", m.group(), m.start(), pos))
                if sections and m.group() == "%%":
                    seen_sections += 1
                    if seen_sections == 2:
                        end = pos
                        break
            elif m := self._name.match(text, pos):
                toks.append(Tok("name", m.group(), pos, m.end()))
                pos = m.end()
            elif m := _INT.match(text, pos):
                toks.append(Tok("int", m.group(), pos, m.end()))
                pos = m.end()
            else:
                for p in self._punct:
                    if text.startswith(p, pos):
                        toks.append(Tok("punct", p, pos, pos + len(p)))
                        pos += len(p)
                        break
                else:
                    raise self.error(f"unexpected character {ch!r}", pos)
        toks.append(Tok("eof", "", end, end))
        return toks
