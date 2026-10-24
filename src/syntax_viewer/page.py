"""HTML for the right pane (FR-7, FR-8, FR-10, FR-11, FR-12, FR-15).

Every symbol occurrence is an `<a href="sym:NAME">` link (NAME URL-quoted).
Qt-free so it can be tested headlessly.
"""

from __future__ import annotations

import html
import re
from urllib.parse import quote, unquote

from syntax_viewer.model import CommentPos, Grammar, Kind, Rule
from syntax_viewer.render import expr_text, rule_text

SCHEME = "sym:"
COLORS = {Kind.NONTERMINAL: "#2563eb", Kind.TERMINAL: "#0f766e", Kind.UNDEFINED: "#dc2626"}
COMMENT_COLOR = "#6b7280"
_IDENT = re.compile(r"[A-Za-z_]\w*(?:-\w+)*")


def href(name: str) -> str:
    return SCHEME + quote(name, safe="")


def name_from_href(url: str) -> str | None:
    return unquote(url[len(SCHEME) :]) if url.startswith(SCHEME) else None


class _Linker:
    def __init__(self, grammar: Grammar):
        self.grammar = grammar
        # Non-identifier symbols (literals, regexes, ...) are matched verbatim.
        others = sorted((n for n in grammar.symbols if not _IDENT.fullmatch(n)), key=len, reverse=True)
        parts = [re.escape(n) for n in others] + [_IDENT.pattern]
        self.pattern = re.compile("|".join(parts))

    def link(self, name: str) -> str:
        sym = self.grammar.symbols.get(name)
        if sym is None:
            return html.escape(name)
        return f'<a href="{html.escape(href(name))}" style="color:{COLORS[sym.kind]}">{html.escape(name)}</a>'

    def source(self, text: str) -> str:
        """Escape source text, linking every known symbol in it."""
        out, pos = [], 0
        for m in self.pattern.finditer(text):
            out.append(html.escape(text[pos : m.start()]))
            out.append(self.link(m.group()) if m.group() in self.grammar.symbols else html.escape(m.group()))
            pos = m.end()
        out.append(html.escape(text[pos:]))
        return "".join(out)


def _comment(text: str) -> str:
    return f'<pre style="color:{COMMENT_COLOR}">{html.escape(text)}</pre>'


_BLANKED_LINE = re.compile(r"\n[ \t]*(?=\n)")
_TRAILING_SPACE = re.compile(r"[ \t]+(?=\n|$)")


def _original(grammar: Grammar, rule: Rule, linker: _Linker) -> str:
    """Source slice of a rule without its actions; links outside its inner
    comments only. Lines emptied by removing an action are dropped."""
    pieces = [(c.span, True) for c in rule.comments if c.pos is CommentPos.INNER]
    pieces += [(s, False) for s in rule.elided]
    out, pos = [], rule.span.start
    for span, is_comment in sorted(pieces, key=lambda p: p[0].start):
        out.append(linker.source(grammar.source[pos : span.start]))
        if is_comment:
            out.append(f'<span style="color:{COMMENT_COLOR}">{html.escape(grammar.source[span.start : span.end])}</span>')
        pos = span.end
    out.append(linker.source(grammar.source[pos : rule.span.end]))
    text = _TRAILING_SPACE.sub("", "".join(out))
    return "<pre>" + _BLANKED_LINE.sub("", text) + "</pre>"


def build_page(grammar: Grammar, name: str, original: bool = False) -> str:
    sym = grammar.symbols[name]
    linker = _Linker(grammar)
    rules = grammar.rules.get(name, [])
    kind = {Kind.NONTERMINAL: "non-terminal", Kind.TERMINAL: "terminal", Kind.UNDEFINED: "undefined"}[sym.kind]
    if name in grammar.lexical:
        kind = "terminal (lexical rule)"
    where = f" · line {sym.span.line}" if sym.span else ""

    parts = [
        f'<h2 style="color:{COLORS[sym.kind]}">{html.escape(name)}</h2>',
        f'<p style="color:{COMMENT_COLOR}">{kind}{where}</p>',
    ]
    if sym.declaration:
        parts.append(f"<p><b>Declared:</b> <code>{html.escape(sym.declaration)}</code></p>")

    comments = [c for r in rules for c in r.comments]
    parts += [_comment(c.text) for c in comments if c.pos is CommentPos.LEADING]
    if rules:
        if original:
            parts += [_original(grammar, r, linker) for r in rules]
        else:
            parts.append("<pre>" + rule_text(grammar, name, linker.link) + "</pre>")
            parts += [_comment(c.text) for c in comments if c.pos is CommentPos.INNER]
    elif sym.definition is not None:
        parts.append("<pre>" + expr_text(sym.definition, 0, linker.link) + "</pre>")
    elif sym.kind is Kind.UNDEFINED:
        parts.append("<p><i>Referenced but never defined.</i></p>")
    elif sym.kind is Kind.TERMINAL:
        parts.append("<p><i>terminal (no definition)</i></p>")
    elif (sym.declaration or "").startswith("%import"):
        parts.append("<p><i>rule defined in another grammar</i></p>")
    else:
        parts.append("<p><i>declared, but has no rules</i></p>")
    parts += [_comment(c.text) for c in comments if c.pos is CommentPos.TRAILING]

    used = sorted(grammar.used_by.get(name, ()), key=str.lower)
    links = ", ".join(linker.link(u) for u in used) if used else "<i>(unused)</i>"
    parts.append(f"<p><b>Used by:</b> {links}</p>")
    return "\n".join(parts)
