from pathlib import Path

import pytest

from syntax_viewer import readers
from syntax_viewer.model import CommentPos, Except, GrammarError, Literal, Opt, Plus, Regex, Seq, Star, SymRef
from syntax_viewer.readers.w3c_ebnf import W3cEbnfReader

FIX = Path(__file__).parent / "fixtures"
w3c = W3cEbnfReader()


def read(text):
    return w3c.read(text, "t.ebnf")


@pytest.fixture(scope="module")
def json_g():
    return readers.load(str(FIX / "json-w3c.ebnf"))


def test_tc26_w3c_basic():
    g = read("expr ::= term ('+' term)*\nterm ::= [0-9]+")
    assert g.body("expr") == Seq((SymRef("term"), Star(Seq((Literal("'+'"), SymRef("term"))))))
    assert g.body("term") == Plus(Regex("[0-9]"))


def test_rules_end_at_next_rule_without_terminator():
    g = read("a ::= b c\nb ::= 'x'\nc ::= 'y'")
    assert g.body("a") == Seq((SymRef("b"), SymRef("c")))


def test_charclass_is_not_optional_and_charcode_is_literal():
    g = read("a ::= [abc] #x20 b?")
    assert g.body("a") == Seq((Regex("[abc]"), Literal("#x20"), Opt(SymRef("b"))))


def test_exception():
    assert read("a ::= Char* - 'x'").body("a") == Except(Star(SymRef("Char")), Literal("'x'"))


@pytest.mark.parametrize("text, line", [("a ::= ( b\n", 2), ("a ::= b\n)\n", 2), ("a ::= b /* open", 1), ("junk", 1)])
def test_tc11_malformed(text, line):
    with pytest.raises(GrammarError) as exc:
        read(text)
    assert exc.value.line == line


def test_tc41_dialect_sniff():
    assert readers.choose("x.ebnf", "a ::= b").name == "ebnf-w3c"
    assert readers.choose("x.ebnf", "a = b ;").name == "ebnf-iso"
    assert readers.choose(str(FIX / "kukel.ebnf"), (FIX / "kukel.ebnf").read_text()).name == "ebnf-iso"
    assert readers.choose(str(FIX / "json-w3c.ebnf"), (FIX / "json-w3c.ebnf").read_text()).name == "ebnf-w3c"


def test_tc53_json_fixture(json_g):
    assert len(json_g.rules) == 15 and json_g.start == "json"
    assert json_g.used_by["value"] == {"array", "json", "member"}


def test_fr15_comments_and_constraints(json_g):
    [lead] = [c for c in json_g.rules["object"][0].comments if c.pos is CommentPos.LEADING]
    assert "name/value pairs" in lead.text
    assert any("VC: Unique Names" in c.text for c in json_g.rules["member"][0].comments)
    assert json_g.rules["json"][0].comments == []  # file header is a section comment


def test_tc29_spans(json_g):
    for name, [r] in json_g.rules.items():
        text = json_g.source[r.span.start : r.span.end]
        assert text.startswith(name) and "::=" in text and not text[-1].isspace()
