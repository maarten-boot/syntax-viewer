"""Qt-free browsing state: filter, selection, history and view mode
(FR-8, FR-9, FR-11, FR-13). The GUI only mirrors this state."""

from __future__ import annotations

from enum import Enum

from syntax_viewer.history import History
from syntax_viewer.model import Grammar, Symbol
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

    def load(self, grammar: Grammar) -> None:
        """Show a new grammar: filter and history are reset (FR-13), the
        start symbol is selected."""
        self.grammar = grammar
        self.filter_text = ""
        self.history.reset()
        if grammar.start:
            self.history.visit(grammar.start)

    @property
    def current(self) -> str | None:
        return self.history.current

    def matches(self, sym: Symbol) -> bool:
        return self.filter_text.lower() in sym.name.lower()

    def visible(self) -> list[Symbol]:
        """Symbols in list order (FR-6), reduced by the filter (FR-9)."""
        if self.grammar is None:
            return []
        return [s for s in self.grammar.sorted_symbols() if self.matches(s)]

    def set_filter(self, text: str) -> None:
        self.filter_text = text

    def _reveal(self, name: str) -> None:
        sym = self.grammar.symbols[name]
        if not self.matches(sym):
            self.filter_text = ""  # FR-9: a hidden target clears the filter

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
