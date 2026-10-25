"""GUI smoke tests on Qt's offscreen platform (skipped without PySide6)."""

import os
import time
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings, QUrl  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from syntax_viewer.gui import MainWindow  # noqa: E402
from syntax_viewer.page import href  # noqa: E402

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def make(app, tmp_path):
    asked = []

    def factory(answer=True):
        settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)

        def ask(parent, path, count):
            asked.append((path, count))
            return answer

        return MainWindow(settings=settings, ask=ask)

    factory.asked = asked
    return factory


def list_names(w):
    return [w.list.item(i).text() for i in range(w.list.count())]


def test_tc01_open_lists_symbols(make):
    w = make()
    assert w.open(str(FIX / "json-w3c.ebnf"))
    assert w.list.currentItem().text() == "json"
    assert "json" in w.view.toPlainText()
    assert "ebnf-w3c" in w.statusBar().currentMessage()


def test_open_error_does_not_crash(make, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    shown = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *a: shown.append(a[2]))
    bad = tmp_path / "bad.ebnf"
    bad.write_text("a = ( b ;")
    w = make()
    assert not w.open(str(bad))
    assert "bad.ebnf:1" in shown[0]


def test_tc18_link_click_selects_in_list(make):
    w = make()
    w.open(str(FIX / "json-w3c.ebnf"))
    w._on_link(QUrl(href("value")))
    assert w.list.currentItem().text() == "value"
    assert w.view.toPlainText().startswith("value")


def test_tc19_literal_link(make):
    w = make()
    w.open(str(FIX / "json-w3c.ebnf"))
    w._on_link(QUrl(href("'{'")))
    assert w.list.currentItem().text() == "'{'"


def test_tc22_link_clears_filter(make):
    w = make()
    w.open(str(FIX / "json-w3c.ebnf"))
    w.filter.setText("arr")
    assert list_names(w) == ["array"]
    w._on_link(QUrl(href("value")))
    assert w.filter.text() == "" and w.list.currentItem().text() == "value"


def test_list_click_navigates(make):
    w = make()
    w.open(str(FIX / "json-w3c.ebnf"))
    w.list.setCurrentRow(list_names(w).index("member"))
    assert w.browser.current == "member" and w.act_back.isEnabled()


def test_tc37_history_buttons(make):
    w = make()
    assert not w.act_back.isEnabled() and not w.act_forward.isEnabled()
    w.open(str(FIX / "json-w3c.ebnf"))
    w.select("value")
    w.select("array")
    w.go_back()
    assert w.browser.current == "value" and w.act_forward.isEnabled()
    w.clear_history()
    assert not w.act_back.isEnabled() and not w.act_forward.isEnabled() and not w.act_clear.isEnabled()
    assert w.act_back.shortcut().toString() == "Alt+Left"
    w.select("member")
    w.open(str(FIX / "kukel.lark"))
    assert not w.act_back.isEnabled()


def test_tc28_view_toggle_persists(make):
    w = make()
    w.open(str(FIX / "json-w3c.ebnf"))
    w.act_original.trigger()
    w._on_link(QUrl(href("value")))
    assert "value    ::=" in w.view.toPlainText()


def test_tc45_uppercase_prompt_remembered(make):
    w = make(answer=True)
    w.open(str(FIX / "kukel.ebnf"))
    assert len(make.asked) == 1 and make.asked[0][1] == 25
    assert w.browser.grammar.symbols["Identifier"].kind.value == "terminal"
    assert w.act_upper.isChecked()
    w2 = make(answer=False)
    w2.open(str(FIX / "kukel.ebnf"))
    assert len(make.asked) == 1  # remembered, not asked again
    assert w2.browser.grammar.symbols["Identifier"].kind.value == "terminal"
    w2.act_upper.trigger()  # switch off via the View menu, remembered
    assert w2.browser.grammar.symbols["Identifier"].kind.value == "nonterminal"
    w3 = make()
    w3.open(str(FIX / "kukel.ebnf"))
    assert w3.browser.grammar.symbols["Identifier"].kind.value == "nonterminal"


def test_no_prompt_for_lark_or_plain_ebnf(make):
    w = make()
    w.open(str(FIX / "kukel.lark"))
    w.open(str(FIX / "BBCBASIC.ebnf"))
    assert make.asked == [] and not w.act_upper.isEnabled()


def test_tc55_reload_as_format(make, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "critical", lambda *a: None)
    w = make()
    w.open(str(FIX / "json-w3c.ebnf"))
    w.reload_as("ebnf-iso")  # wrong dialect: error shown, previous grammar kept
    assert w.browser.grammar.format == "ebnf-w3c"


def test_tc25_filter_performance(make, tmp_path):
    src = "\n".join(f'r{i} = r{i + 1} , {{ "x{i}" }} ;' for i in range(1000))
    f = tmp_path / "big.ebnf"
    f.write_text(src)
    w = make()
    t = time.perf_counter()
    w.open(str(f))
    w.filter.setText("r99")
    w.filter.setText("")
    assert time.perf_counter() - t < 1.0


def test_tc54_selected_item_scrolled_into_view(make, app):
    w = make()
    w.resize(900, 400)
    w.show()
    w.open(str(FIX / "kukel.ebnf"))
    w._on_link(QUrl(href("Identifier")))
    app.processEvents()
    item = w.list.currentItem()
    assert item.text() == "Identifier"
    assert w.list.viewport().rect().intersects(w.list.visualItemRect(item))


def test_tc67_kind_and_regex_controls(make):
    from syntax_viewer.model import Kind

    w = make()
    w.open(str(FIX / "json-w3c.ebnf"))
    w.kind_boxes[Kind.TERMINAL].setChecked(False)
    assert all(not n.startswith(("'", "[", "#")) for n in list_names(w))
    w.regex_button.setChecked(True)
    w.filter.setText("^(object|array)$")
    assert sorted(list_names(w)) == ["array", "object"]
    w.filter.setText("obj(")
    assert "dc2626" in w.filter.styleSheet() and "Invalid regular expression" in w.filter.toolTip()
    assert sorted(list_names(w)) == ["array", "object"]
    w._on_link(QUrl(href("'{'")))  # hidden terminal: kind re-checked, text filter cleared
    assert w.kind_boxes[Kind.TERMINAL].isChecked() and w.filter.text() == "" and w.filter.styleSheet() == ""
    assert w.list.currentItem().text() == "'{'"
    w.kind_boxes[Kind.UNDEFINED].setChecked(False)
    w.open(str(FIX / "BBCBASIC.ebnf"))
    assert not w.kind_boxes[Kind.UNDEFINED].isChecked() and w.regex_button.isChecked()
    assert "EOL" not in [n.lstrip("⚠ ") for n in list_names(w)]
