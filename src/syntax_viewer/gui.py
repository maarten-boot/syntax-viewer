"""PySide6 main window (FR-1, FR-6…FR-15). All browsing logic lives in
`Browser`; this module only mirrors its state into widgets."""

from __future__ import annotations

import os
import sys
from typing import Callable

from PySide6.QtCore import QSettings, Qt, QUrl
from PySide6.QtGui import QAction, QBrush, QColor, QFont, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from syntax_viewer import readers
from syntax_viewer.browser import Browser, View
from syntax_viewer.model import Grammar, GrammarError, Kind
from syntax_viewer.page import COLORS, name_from_href

FILE_FILTER = "Grammars (*.lark *.ebnf *.iso *.w3c *.y *.yy *.ypp *.bison *.lemon);;All files (*)"
_MARK = {Kind.NONTERMINAL: "", Kind.TERMINAL: "", Kind.UNDEFINED: "⚠ "}

# Asks whether upper-case rules should be terminals (FR-14); returns True/False.
AskUppercase = Callable[[QWidget, str, int], bool]


def ask_uppercase(parent: QWidget, path: str, count: int) -> bool:
    answer = QMessageBox.question(
        parent,
        "Upper-case rules",
        f"{os.path.basename(path)} has {count} rules whose names start with an upper-case "
        "letter and that only use other upper-case rules.\n\n"
        "Treat them as lexical rules (terminals)?\n\n"
        "This is remembered for this file and can be changed in the View menu.",
    )
    return answer == QMessageBox.StandardButton.Yes


class MainWindow(QMainWindow):
    def __init__(self, settings: QSettings | None = None, ask: AskUppercase = ask_uppercase):
        super().__init__()
        self.settings = settings or QSettings("syntax-viewer", "syntax-viewer")
        self.ask = ask
        self.browser = Browser()
        self.path: str | None = None
        self.format: str | None = None
        self._syncing = False

        self.setWindowTitle("syntax-viewer")
        self.resize(1100, 700)
        self._build_widgets()
        self._build_actions()
        self.refresh()

    # -- construction --

    def _build_widgets(self) -> None:
        self.filter = QLineEdit(placeholderText="Filter symbols…", clearButtonEnabled=True)
        self.filter.textChanged.connect(self._on_filter)
        self.list = QListWidget()
        self.list.currentItemChanged.connect(self._on_list_selection)
        left = QWidget()
        layout = QVBoxLayout(left)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.filter)
        layout.addWidget(self.list)

        self.view = QTextBrowser(openLinks=False)
        self.view.anchorClicked.connect(self._on_link)
        mono = QFont("monospace")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self.view.document().setDefaultFont(mono)

        split = QSplitter()
        split.addWidget(left)
        split.addWidget(self.view)
        split.setSizes([300, 800])
        self.setCentralWidget(split)

    def _action(self, text: str, slot, shortcut=None, checkable=False) -> QAction:
        act = QAction(text, self, checkable=checkable)
        if shortcut:
            act.setShortcut(QKeySequence(shortcut))
        act.triggered.connect(slot)
        return act

    def _build_actions(self) -> None:
        self.act_open = self._action("&Open…", self.open_dialog, QKeySequence.StandardKey.Open)
        self.act_back = self._action("&Back", self.go_back, "Alt+Left")
        self.act_forward = self._action("&Forward", self.go_forward, "Alt+Right")
        self.act_clear = self._action("&Clear history", self.clear_history)
        self.act_original = self._action("&Original source", self._on_view_toggle, "Ctrl+U", checkable=True)
        self.act_upper = self._action("&Upper-case rules are terminals", self._on_upper_toggle, checkable=True)
        self.act_filter = self._action("&Find symbol", self.filter.setFocus, QKeySequence.StandardKey.Find)

        menu = self.menuBar()
        file_menu = menu.addMenu("&File")
        file_menu.addAction(self.act_open)
        self.format_menu = file_menu.addMenu("Reload &as format")
        for reader in sorted(readers.readers(), key=lambda r: r.name):
            file_menu_act = self.format_menu.addAction(reader.name)
            file_menu_act.triggered.connect(lambda _=False, n=reader.name: self.reload_as(n))
        file_menu.addSeparator()
        file_menu.addAction(self._action("&Quit", self.close, QKeySequence.StandardKey.Quit))
        view_menu = menu.addMenu("&View")
        view_menu.addActions([self.act_original, self.act_upper, self.act_filter])
        go_menu = menu.addMenu("&Go")
        go_menu.addActions([self.act_back, self.act_forward, self.act_clear])

        bar = self.addToolBar("Main")
        bar.setObjectName("main-toolbar")
        bar.addActions([self.act_open, self.act_back, self.act_forward, self.act_clear])
        bar.addSeparator()
        bar.addAction(self.act_original)

    # -- loading (FR-1, FR-2, FR-14) --

    def open_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open grammar", os.path.dirname(self.path or ""), FILE_FILTER)
        if path:
            self.open(path)

    def reload_as(self, fmt: str) -> None:
        if self.path:
            self.open(self.path, fmt)

    def open(self, path: str, fmt: str | None = None) -> bool:
        try:
            grammar = readers.load(path, fmt)
        except (GrammarError, OSError) as exc:
            QMessageBox.critical(self, "Cannot open grammar", str(exc))
            return False
        self.path, self.format = os.path.abspath(path), fmt
        self._apply_uppercase_setting(grammar)
        self.browser.load(grammar)
        self.setWindowTitle(f"{os.path.basename(path)} — syntax-viewer")
        self.refresh()
        return True

    def _settings_key(self) -> str:
        return "uppercase-terminals/" + self.path.replace("/", "|")

    def _apply_uppercase_setting(self, grammar: Grammar) -> None:
        candidates = grammar.lexical_candidates()
        if not candidates:
            return
        stored = self.settings.value(self._settings_key())
        if stored is None:
            stored = "yes" if self.ask(self, self.path, len(candidates)) else "no"
            self.settings.setValue(self._settings_key(), stored)
        if stored == "yes":
            grammar.set_lexical(candidates)

    def _on_upper_toggle(self, checked: bool) -> None:
        grammar = self.browser.grammar
        if grammar is None:
            return
        upper = {n for n in grammar.rules if n[:1].isupper()}
        grammar.set_lexical(upper if checked else set())
        self.settings.setValue(self._settings_key(), "yes" if checked else "no")
        self.refresh()

    # -- navigation --

    def _on_filter(self, text: str) -> None:
        self.browser.set_filter(text)
        self.refresh()

    def _on_list_selection(self, item: QListWidgetItem | None, _prev=None) -> None:
        if self._syncing or item is None:
            return
        self.browser.navigate(item.data(Qt.ItemDataRole.UserRole))
        self.refresh()

    def _on_link(self, url: QUrl) -> None:
        name = name_from_href(url.toString(QUrl.ComponentFormattingOption.FullyEncoded))
        if name and self.browser.navigate(name):
            self.refresh()

    def select(self, name: str) -> bool:
        ok = self.browser.navigate(name)
        self.refresh()
        return ok

    def go_back(self) -> None:
        self.browser.back()
        self.refresh()

    def go_forward(self) -> None:
        self.browser.forward()
        self.refresh()

    def clear_history(self) -> None:
        self.browser.history.clear()
        self.refresh()

    def _on_view_toggle(self, checked: bool) -> None:
        self.browser.view = View.ORIGINAL if checked else View.NORMALISED
        self.refresh()

    # -- state → widgets --

    def refresh(self) -> None:
        b = self.browser
        self._syncing = True
        try:
            if self.filter.text() != b.filter_text:  # e.g. cleared by a link (FR-9)
                self.filter.blockSignals(True)
                self.filter.setText(b.filter_text)
                self.filter.blockSignals(False)
            self.list.clear()
            current_item = None
            for sym in b.visible():
                item = QListWidgetItem(_MARK[sym.kind] + sym.name)
                item.setData(Qt.ItemDataRole.UserRole, sym.name)
                item.setForeground(QBrush(QColor(COLORS[sym.kind])))
                if sym.kind is Kind.NONTERMINAL:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                item.setToolTip(sym.kind.value + (" (lexical rule)" if sym.name in b.grammar.lexical else ""))
                self.list.addItem(item)
                if sym.name == b.current:
                    current_item = item
            if current_item is not None:
                self.list.setCurrentItem(current_item)
                self.list.scrollToItem(current_item, QListWidget.ScrollHint.PositionAtCenter)
        finally:
            self._syncing = False

        self.view.setHtml(b.page())
        g = b.grammar
        self.act_back.setEnabled(b.history.can_back())
        self.act_forward.setEnabled(b.history.can_forward())
        self.act_clear.setEnabled(b.history.can_back() or b.history.can_forward())
        self.format_menu.setEnabled(g is not None)
        self.act_upper.setEnabled(g is not None and not g.native_terminals and any(n[:1].isupper() for n in g.rules))
        self.act_upper.setChecked(bool(g and g.lexical and not g.native_terminals))
        if g:
            counts = {k: sum(s.kind is k for s in g.symbols.values()) for k in Kind}
            self.statusBar().showMessage(
                f"{g.format} · {counts[Kind.NONTERMINAL]} non-terminals · {counts[Kind.TERMINAL]} terminals"
                + (f" · {counts[Kind.UNDEFINED]} undefined" if counts[Kind.UNDEFINED] else "")
                + f" · {len(b.visible())} shown"
            )


def run(path: str | None = None, fmt: str | None = None) -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    window = MainWindow()
    window.show()
    if path:
        window.open(path, fmt)
    return app.exec()
