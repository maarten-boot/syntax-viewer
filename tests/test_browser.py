"""Controller (Browser) and right-pane page tests — no Qt needed."""

import re
from pathlib import Path

import pytest

from syntax_viewer import readers
from syntax_viewer.browser import Browser, View
from syntax_viewer.page import build_page, href, name_from_href

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture
def b():
    br = Browser()
    br.load(readers.load(str(FIX / "json-w3c.ebnf")))
    return br


def names(b):
    return [s.name for s in b.visible()]


def links(page):
    return {name_from_href(h) for h in re.findall(r'href="([^"]+)"', page)}


def test_load_selects_start(b):
    assert b.current == "json" and not b.history.can_back()


def test_tc20_filter_narrows(b):
    b.set_filter("ARR")
    assert names(b) == ["array"]


def test_tc21_clear_filter_keeps_selection(b):
    b.navigate("value")
    b.set_filter("arr")
    b.set_filter("")
    assert b.current == "value" and len(names(b)) == len(b.grammar.symbols)


def test_tc22_link_to_hidden_symbol_clears_filter(b):
    b.set_filter("arr")
    assert b.navigate("value")
    assert b.filter_text == "" and "value" in names(b)


def test_back_to_hidden_symbol_clears_filter(b):
    b.navigate("value")
    b.navigate("array")
    b.set_filter("arr")
    assert b.back() == "value" and b.filter_text == ""


def test_navigate_unknown_symbol(b):
    assert not b.navigate("nope") and b.current == "json"


def test_new_file_resets_history_and_filter(b):
    b.navigate("value")
    b.set_filter("x")
    b.load(readers.load(str(FIX / "kukel.lark")))
    assert b.current == "start" and not b.history.can_back() and b.filter_text == ""


def test_href_roundtrip():
    for n in ["expr", "'+'", '"a" .. "z"', "/[0-9]+/", "? x ?", "a%b"]:
        assert name_from_href(href(n)) == n


def test_tc17_tc08_page_links_every_symbol(b):
    page = build_page(b.grammar, "object")
    assert {"object", "ws", "member", "'{'", "','", "'}'"} <= links(page)
    assert "Used by:" in page and "value" in links(page.split("Used by:")[1])


def test_tc23_terminal_page(b):
    page = build_page(b.grammar, "'{'")
    assert "terminal (no definition)" in page and "Used by:" in page


def test_tc32_unused_page(b):
    assert "(unused)" in build_page(b.grammar, "json")


def test_fr15_comments_on_page(b):
    assert "name/value pairs" in build_page(b.grammar, "object")
    assert "VC: Unique Names" in build_page(b.grammar, "member")


def test_tc28_original_view_links(b):
    b.navigate("value")
    b.view = View.ORIGINAL
    page = b.page()
    assert "value    ::= object | array" in re.sub(r"<[^>]+>", "", page)
    assert {"object", "array", "'true'"} <= links(page)


def test_original_view_does_not_link_inside_inner_comments():
    g = readers.load(str(FIX / "BBCBASIC.ebnf"))
    page = build_page(g, "type-suffix", original=True)
    inner = re.search(r"<span[^>]*>\(\* 32-bit integer.*?</span>", page).group()
    assert "href" not in inner


def test_lexical_terminal_page():
    g = readers.load(str(FIX / "kukel.lark"))
    page = build_page(g, "WHITESPACE")
    assert "terminal (lexical rule)" in page and "%ignore" in page


def test_undefined_page():
    g = readers.load(str(FIX / "BBCBASIC.ebnf"))
    assert "never defined" in build_page(g, "EOL")
