from pathlib import Path

import pytest

from syntax_viewer import readers
from syntax_viewer.model import CommentPos, GrammarError, Kind, Literal, Opt, Plus, Range, Regex, Repeat, Seq, SymRef
from syntax_viewer.readers.lark import LarkReader
from syntax_viewer.render import rule_text

FIX = Path(__file__).parent / "fixtures"
lark_reader = LarkReader()


def read(text):
    return lark_reader.read(text, "t.lark")


@pytest.fixture(scope="module")
def kukel():
    return readers.load(str(FIX / "kukel.lark"))


def test_tc10_rules_terminals_import():
    g = read('start: expr+\nexpr: NUMBER\nNUMBER: /\\d+/\n%import common.WS\n%ignore WS\n')
    assert g.body("start") == Plus(SymRef("expr"))
    num = g.symbols["NUMBER"]
    assert num.kind is Kind.TERMINAL and num.definition == Regex("/\\d+/")
    assert g.symbols["WS"].kind is Kind.TERMINAL
    assert g.symbols["WS"].declaration == "%import common.WS; %ignore"
    assert g.start == "start"


def test_tc52_prefixes_alias_continuation_and_brackets():
    g = read('?a: b "x"? -> one\n | [c] d ~ 2..3 -> two\n!b: "k"i | "a".."z"\nc: B\nd: B\nB: "b"\n')
    assert "a" in g.rules and "b" in g.rules
    assert "one" not in g.symbols and "two" not in g.symbols  # aliases are not symbols
    assert g.body("a").options[0] == Seq((SymRef("b"), Opt(Literal('"x"'))))
    assert g.body("a").options[1] == Seq((Opt(SymRef("c")), Repeat(2, SymRef("d"), 3)))
    assert g.body("b").options == (Literal('"k"i'), Range('"a"', '"z"'))
    assert rule_text(g, "a").splitlines()[1].strip() == "| c? 2..3 * d"


def test_import_forms_and_declare():
    g = read("start: A B x\n%import common (A, B)\n%import .other.rule -> x\n%declare C\n")
    assert g.symbols["A"].kind is g.symbols["B"].kind is Kind.TERMINAL
    assert g.symbols["x"].kind is Kind.NONTERMINAL and g.symbols["x"].declaration.startswith("%import .other")
    assert g.symbols["C"].kind is Kind.TERMINAL


def test_override_and_extend():
    g = read("start: a\na: X\n%override a: Y\n%extend a: Z\n")
    assert g.body("a").options == (SymRef("Y"), SymRef("Z"))


def test_multiline_parens():
    g = read("start: (\n  a\n  | b\n)\na: A\nb: B\n")
    assert g.body("start").options == (SymRef("a"), SymRef("b"))


@pytest.mark.parametrize(
    "text, line",
    [("start: a\nb c\n", 2), ("start: (a\n", 2), ("start a\n", 1), ("start: a\n%frobnicate x\n", 2), ("t{x}: x\n", 1)],
)
def test_tc11_malformed(text, line):
    with pytest.raises(GrammarError) as exc:
        read(text)
    assert exc.value.line == line


def test_tc03_detection():
    assert readers.choose("g.lark", "start: a\n").name == "lark"


# -- kukel.lark fixture -----------------------------------------------------


def test_tc40_kukel(kukel):
    assert len([n for n in kukel.rules if n not in kukel.lexical]) == 89
    assert len(kukel.lexical) == 16
    assert kukel.start == "start"
    assert "statement" in kukel.rules and "expression_statement" not in kukel.symbols
    assert "%ignore" in kukel.symbols["WHITESPACE"].declaration
    assert kukel.symbols["LABEL"].declaration == "priority 2"
    assert not any(s.kind is Kind.UNDEFINED for s in kukel.symbols.values())


def test_fr14_not_offered_for_lark(kukel):
    assert kukel.native_terminals and kukel.lexical_candidates() == set()


def test_fr15_merged_line_comments(kukel):
    [c] = [c for c in kukel.rules["LABEL"][0].comments if c.pos is CommentPos.LEADING]
    assert c.text.count("//") == 3


def test_tc29_spans(kukel):
    for name, rules in kukel.rules.items():
        for r in rules:
            text = kukel.source[r.span.start : r.span.end]
            assert text.lstrip("?!").startswith(name), name
            assert not text.endswith("\n")


def test_tc51_rule_names_match_lark_library(kukel):
    lark = pytest.importorskip("lark")
    parser = lark.Lark((FIX / "kukel.lark").read_text(), parser="lalr", lexer="contextual")
    theirs = {r.origin.name for r in parser.rules if not r.origin.name.startswith("__")}
    assert theirs == {n for n in kukel.rules if n not in kukel.lexical}
    assert kukel.lexical <= {t.name for t in parser.terminals}


def test_cli_auto_keeps_lark_terminals(capsys):
    from syntax_viewer.cli import main

    main(["--dump", str(FIX / "kukel.lark")])
    assert "WHITESPACE  [terminal]" in capsys.readouterr().out


def test_tc59_imported_rule_page():
    from syntax_viewer.page import build_page

    g = read("start: x\n%import .other.rule -> x\n")
    assert "rule defined in another grammar" in build_page(g, "x")
