from pathlib import Path

import pytest

from syntax_viewer import readers
from syntax_viewer.model import (
    CommentPos,
    Except,
    GrammarError,
    Kind,
    Literal,
    Opt,
    Range,
    Repeat,
    Seq,
    Special,
    Star,
    SymRef,
)
from syntax_viewer.readers.iso_ebnf import IsoEbnfReader
from syntax_viewer.render import rule_text

FIX = Path(__file__).parent / "fixtures"
iso = IsoEbnfReader()


def read(text):
    return iso.read(text, "t.ebnf")


@pytest.fixture(scope="module")
def kukel():
    return readers.load(str(FIX / "kukel.ebnf"))


@pytest.fixture(scope="module")
def bbc():
    return readers.load(str(FIX / "BBCBASIC.ebnf"))


def comments(g, name, pos):
    return [c.text for r in g.rules[name] for c in r.comments if c.pos is pos]


# -- syntax -----------------------------------------------------------------


def test_tc27_iso_operators():
    g = read('expr = term , { "+" , term } ;\nopt = [ x ] ;\n')
    assert g.body("expr") == Seq((SymRef("term"), Star(Seq((Literal('"+"'), SymRef("term"))))))
    assert g.body("opt") == Opt(SymRef("x"))


def test_juxtaposition_equals_comma():
    assert read("a = b c ;").body("a") == read("a = b , c ;").body("a")


def test_exception_range_special_repeat_hyphen():
    g = read('a = b - c ;\nr = "a" .. "z" ;\ns = ? any char ? ;\nn = 3 * ( "," x ) ;\nname-start = up-per ;')
    assert g.body("a") == Except(SymRef("b"), SymRef("c"))
    assert g.body("r") == Range('"a"', '"z"')
    assert g.body("s") == Special("? any char ?")
    assert g.body("n") == Repeat(3, Seq((Literal('","'), SymRef("x"))))
    assert g.body("name-start") == SymRef("up-per")
    assert rule_text(g, "n") == 'n ::= 3 * ( "," x )'


def test_nested_comment_skipped():
    g = read("(* outer (* inner *) still outer *)\na = b ;")
    assert list(g.rules) == ["a"]


def test_empty_alternative():
    assert "ε" in rule_text(read("a = b | ;"), "a")


@pytest.mark.parametrize(
    "text, line",
    [("a = b ;\nc = d\ne = f ;", 3), ("a = ( b ;", 1), ('a = "b ;', 1), ("a = b ;\n(* open", 2)],
)
def test_tc11_malformed(text, line):
    with pytest.raises(GrammarError) as exc:
        read(text)
    assert exc.value.line == line and exc.value.path == "t.ebnf"


# -- detection --------------------------------------------------------------


def test_tc03_tc41_detection():
    assert readers.choose("x.ebnf", "a = b ;").name == "ebnf-iso"
    assert iso.detect("x.ebnf", "a ::= b") < iso.detect("x.ebnf", "a = b ;")


# -- real fixtures ----------------------------------------------------------


def test_tc38_kukel(kukel):
    assert len(kukel.rules) == 89
    assert kukel.start == "start"
    assert isinstance(kukel.body("Identifier"), Except)


def test_tc39_bbcbasic(bbc):
    assert bbc.body("upper") == Range('"A"', '"Z"')
    assert isinstance(bbc.body("string-char"), Special)
    assert "name-start" in bbc.rules
    assert bbc.symbols["EOL"].kind is Kind.UNDEFINED  # described only in prose


# -- FR-14 uppercase-lexical convention -------------------------------------


def test_tc42_detect_convention(kukel):
    cands = kukel.lexical_candidates()
    assert len(cands) == 25 and "Identifier" in cands


def test_tc43_no_false_positive(bbc):
    assert bbc.lexical_candidates() == set()


def test_tc44_apply_convention(kukel):
    used = set(kukel.used_by["Identifier"])
    kukel.set_lexical(kukel.lexical_candidates())
    sym = kukel.symbols["Identifier"]
    assert sym.kind is Kind.TERMINAL and sym.definition == kukel.body("Identifier")
    assert kukel.used_by["Identifier"] == used
    kukel.set_lexical(set())
    assert kukel.symbols["Identifier"].kind is Kind.NONTERMINAL


# -- FR-15 comments -----------------------------------------------------------


def test_tc46_trailing(kukel):
    assert any("A global without an initializer is nil" in c for c in comments(kukel, "global_variable", CommentPos.TRAILING))


def test_tc47_inner(bbc):
    assert any("32-bit integer" in c for c in comments(bbc, "type-suffix", CommentPos.INNER))


def test_tc48_section_comment_not_attached():
    g = read("a = b ;\n\n(* section *)\n\nc = d ;")
    assert g.rules["a"][0].comments == [] and g.rules["c"][0].comments == []


def test_tc49_leading():
    g = read("a = b ;\n\n(* doc *)\nc = d ;")
    assert comments(g, "c", CommentPos.LEADING) == ["(* doc *)"]


def test_trailing_chain_and_same_line():
    g = read("a = b ;   (* one *)\n      (* two *)\nc = d ;")
    assert comments(g, "a", CommentPos.TRAILING) == ["(* one *)", "(* two *)"]


def test_tc29_source_spans(kukel, bbc):
    r = kukel.rules["global_variable"][0]
    assert kukel.source[r.span.start : r.span.end] == 'global_variable     = Identifier , [ "=" , assignment ] ;'
    for g in (kukel, bbc):
        for name, rules in g.rules.items():
            for r in rules:
                text = g.source[r.span.start : r.span.end]
                assert text.startswith(name) and text.rstrip().endswith((";", "."))
                assert g.source.count("\n", 0, r.span.start) + 1 == r.span.line


def test_tc25_performance_2000_rules():
    import time

    src = "\n".join(f'r{i} = r{i + 1} , {{ "x" | r{(i * 7) % 2000} }} , [ T{i % 50} ] ;' for i in range(2000))
    t = time.perf_counter()
    g = read(src)
    assert time.perf_counter() - t < 1.0 and len(g.rules) == 2000


def test_fr14_not_for_native_terminal_formats(kukel):
    kukel.native_terminals = True
    try:
        assert kukel.lexical_candidates() == set()
    finally:
        kukel.native_terminals = False
