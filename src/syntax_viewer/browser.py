"""Qt-free browsing state: filter, selection, history and view mode
(FR-8, FR-9, FR-11, FR-13, FR-16, FR-17). The GUI only mirrors this state."""

from __future__ import annotations

import re
from enum import Enum

from syntax_viewer.history import History
from syntax_viewer.model import Grammar, Kind, Symbol
from syntax_viewer.page import build_page


class View(Enum):
    NORMALISED = "normalised"
    ORIGINAL = "original"


class Browser:
    def __init__(self) -> None:
        self.grammar: Grammar | None = None
        self.filter_text = ""
        self.history = History()
        self.view = View.NORMALISED
        self.kinds: set[Kind] = set(Kind)  # FR-16
        self.regex = False  # FR-17
        self.filter_error: str | None = None  # invalid regex message
        self._pattern = re.compile("")  # last valid regex

    def load(self, grammar: Grammar) -> None:
        """Show a new grammar: text filter and history are reset (FR-13), the
        kind filter and regex mode are kept; the start symbol is selected."""
        self.grammar = grammar
        self.set_filter("")
        self.history.reset()
        if grammar.start:
            self.history.visit(grammar.start)

    @property
    def current(self) -> str | None:
        return self.history.current

    def matches_text(self, sym: Symbol) -> bool:
        if self.regex:
            return self._pattern.search(sym.name) is not None
        return self.filter_text.lower() in sym.name.lower()

    def matches(self, sym: Symbol) -> bool:
        return sym.kind in self.kinds and self.matches_text(sym)

    def visible(self) -> list[Symbol]:
        """Symbols in list order (FR-6), reduced by the filter (FR-9)."""
        if self.grammar is None:
            return []
        return [s for s in self.grammar.sorted_symbols() if self.matches(s)]

    def set_filter(self, text: str) -> None:
        """Set the text filter. In regex mode an invalid pattern sets
        `filter_error` and keeps the last valid pattern (FR-17)."""
        self.filter_text = text
        self.filter_error = None
        if self.regex:
            try:
                self._pattern = re.compile(text, re.IGNORECASE)
            except re.error as exc:
                self.filter_error = str(exc)

    def set_regex(self, on: bool) -> None:
        self.regex = on
        self._pattern = re.compile("")
        self.set_filter(self.filter_text)

    def set_kind(self, kind: Kind, shown: bool) -> None:
        if shown:
            self.kinds.add(kind)
        else:
            self.kinds.discard(kind)

    def _reveal(self, name: str) -> None:
        """FR-9: make a navigation target visible in the list."""
        sym = self.grammar.symbols[name]
        if not self.matches_text(sym):
            self.set_filter("")
        self.kinds.add(sym.kind)

    def navigate(self, name: str) -> bool:
        """Select a symbol from the list or a link; records history."""
        if self.grammar is None or name not in self.grammar.symbols:
            return False
        self._reveal(name)
        self.history.visit(name)
        return True

    def back(self) -> str | None:
        name = self.history.back()
        if name:
            self._reveal(name)
        return name

    def forward(self) -> str | None:
        name = self.history.forward()
        if name:
            self._reveal(name)
        return name

    def page(self) -> str:
        if self.grammar is None or self.current is None:
            return ""
        return build_page(self.grammar, self.current, original=self.view is View.ORIGINAL)
