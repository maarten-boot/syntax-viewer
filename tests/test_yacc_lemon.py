import re
from pathlib import Path

import pytest

from syntax_viewer import readers
from syntax_viewer.model import Alt, Empty, GrammarError, Kind, Literal, Seq, SymRef
from syntax_viewer.page import build_page
from syntax_viewer.readers.lemon import LemonReader
from syntax_viewer.readers.yacc import YaccReader

FIX = Path(__file__).parent / "fixtures"
yacc, lemon = YaccReader(), LemonReader()


@pytest.fixture(scope="module")
def calc():
    return readers.load(str(FIX / "calc-bison.y"))


@pytest.fixture(scope="module")
def c99():
    return readers.load(str(FIX / "c99.y"))


@pytest.fixture(scope="module")
def sqlite():
    return readers.load(str(FIX / "sqlite-parse.y"))


def plain(html):
    return re.sub(r"<[^>]+>", "", html).replace("&#x27;", "'").replace("&quot;", '"')


# -- detection (TC-04) ------------------------------------------------------


def test_tc04_disambiguate_dot_y(calc, c99, sqlite):
    assert calc.format == c99.format == "yacc"
    assert sqlite.format == "lemon"


def test_yacc_with_rule_like_comment_stays_yacc():
    text = "/* a ::= b . */\n%%\na: B ;\n"
    assert readers.choose("g.y", text).name == "yacc"


# -- Yacc / Bison -----------------------------------------------------------


def test_tc06_basic_rules():
    g = yacc.read("%token NUM\n%%\nexpr : expr '+' term | term ;\nterm : NUM ;\n")
    assert g.body("expr") == Alt((Seq((SymRef("expr"), Literal("'+'"), SymRef("term"))), SymRef("term")))
    assert g.symbols["'+'"].kind is Kind.TERMINAL and g.symbols["term"].kind is Kind.NONTERMINAL


def test_tc07_actions_and_code_skipped(calc):
    assert set(calc.rules) == {"input", "line", "exp", "assign", "stmt"}
    assert calc.body("exp").options[-1] == Seq((SymRef("exp"), Literal("'\\''"), SymRef("exp")))
    assert "main" not in calc.symbols and "yyerror" not in calc.symbols  # prologue / epilogue


def test_tc08_tokens_empty_error(calc):
    assert calc.body("input").options[0] == Empty()
    assert calc.symbols["NUM"].declaration == '%token <double> NUM; alias "number"'
    assert calc.symbols['"+"'].declaration == "alias of PLUS"
    assert calc.symbols["error"].kind is Kind.TERMINAL
    assert calc.symbols["NAME"].kind is Kind.UNDEFINED  # never declared
    assert calc.used_by["UNUSED"] == set()


def test_yacc_start_and_precedence(calc):
    assert calc.start == "input"
    assert "%left" in calc.symbols["'*'"].declaration
    assert calc.symbols["exp"].declaration == "%nterm <double> exp"


def test_missing_semicolon_between_rules(calc):
    assert calc.body("assign") == Seq((SymRef("NAME"), Literal("'='"), SymRef("exp")))
    assert calc.body("stmt") == Alt((SymRef("assign"), SymRef("exp")))


def test_tc58_original_view_strips_actions(calc):
    page = plain(build_page(calc, "exp", original=True))
    assert "printf" not in page and "$$" not in page and "yyerror" not in page
    assert "| exp MINUS exp\n" in page
    assert "\n\n" not in page.split("exp[result]:")[1].split("Used by")[0].strip()


def test_fr15_yacc_comments(calc):
    assert [c.text for c in calc.rules["line"][0].comments] == ["/* One line of input. */"]


def test_tc56_c99(c99):
    assert len(c99.rules) == 68 and c99.start == "translation_unit"
    assert not any(s.kind is Kind.UNDEFINED for s in c99.symbols.values())
    assert c99.used_by["IDENTIFIER"] >= {"primary_expression", "postfix_expression"}


@pytest.mark.parametrize(
    "text, line",
    [
        ("%token A\na : A ;\n", 3),  # no %%
        ("%%\na : A { unterminated ;\n", 2),
        ("%{\nint x;\n", 1),
        ("%%\n: A ;\n", 2),
        ("%%\na : 'x ;\n", 2),
    ],
)
def test_tc11_yacc_malformed(text, line):
    with pytest.raises(GrammarError) as exc:
        yacc.read(text, "t.y")
    assert exc.value.line == line


# -- Lemon ------------------------------------------------------------------


def test_tc09_lemon_rule():
    g = lemon.read("expr(A) ::= expr(B) PLUS term(C). { A = B + C; }\nterm ::= NUM.\n")
    assert g.body("expr") == Seq((SymRef("expr"), SymRef("PLUS"), SymRef("term")))
    assert g.symbols["PLUS"].kind is Kind.TERMINAL  # upper-case = terminal, no %token needed


def test_lemon_multiterminal_empty_and_precedence():
    g = lemon.read("a ::= .\na ::= ID|INDEXED b. [OR] {x();}\nb ::= B.\n")
    assert g.body("a") == Alt((Empty(), Seq((Alt((SymRef("ID"), SymRef("INDEXED"))), SymRef("b")))))


def test_lemon_conditionals_and_directives():
    g = lemon.read(
        "%include { int x = '}'; }\n%name P\n%token_prefix TK_\n%if !A && B\n"
        "%start_symbol s\n%endif\n%token_class id ID|IDX.\n%fallback ID X Y.\n%wildcard ANY.\ns ::= id X.\n"
    )
    assert g.start == "s"
    assert g.symbols["id"].definition == Alt((SymRef("ID"), SymRef("IDX")))
    assert g.symbols["X"].declaration == "%fallback → ID"


def test_tc57_sqlite(sqlite):
    assert len(sqlite.rules) == 134 and sum(len(r) for r in sqlite.rules.values()) == 416
    assert sqlite.start == "input"
    assert not any(s.kind is Kind.UNDEFINED for s in sqlite.symbols.values())
    assert sqlite.symbols["transtype"].declaration == "%type {int}"
    assert sqlite.symbols["ANY"].declaration == "%wildcard"
    assert sqlite.body("trans_opt").options[0] == Empty()


def test_tc58_sqlite_original_view_excludes_actions(sqlite):
    page = plain(build_page(sqlite, "explain", original=True))
    assert "explain ::= EXPLAIN." in page and "pReprepare" not in page


def test_sqlite_comments(sqlite):
    assert any(c.pos for rs in sqlite.rules.values() for r in rs for c in r.comments)


def test_tc29_lemon_yacc_spans(sqlite, calc):
    for g, end in ((sqlite, "."), (calc, None)):
        for name, rules in g.rules.items():
            for r in rules:
                text = g.source[r.span.start : r.span.end]
                assert text.startswith(name)
                if end:
                    assert text.endswith(end)


@pytest.mark.parametrize(
    "text, line", [("a ::= b\n", 2), ("a ::= b(.\n", 1), ("%token A B\na ::= A.\n", 2), ("a ::= B. { open\n", 1)]
)
def test_tc11_lemon_malformed(text, line):
    with pytest.raises(GrammarError) as exc:
        lemon.read(text, "t.y")
    assert exc.value.line == line


def test_tc13_same_grammar_across_formats(tmp_path):
    """The calculator core in every format yields the same rule structure."""
    sources = {
        "c.lark": 'expr: expr "+" term | term\nterm: NUM\nNUM: /[0-9]+/\n',
        "c.ebnf": 'expr = expr , "+" , term | term ;\nterm = NUM ;\nNUM = digit ;\ndigit = "0" ;\n',
        "c.w3c": "expr ::= expr '+' term | term\nterm ::= NUM\nNUM ::= [0-9]+\n",
        "c.y": "%token NUM\n%%\nexpr : expr '+' term | term ;\nterm : NUM ;\n",
        "c.lemon": "expr ::= expr PLUS term.\nexpr ::= term.\nterm ::= NUM.\n",
    }
    shapes = set()
    for name, src in sources.items():
        f = tmp_path / name
        f.write_text(src)
        g = readers.load(str(f))
        if g.native_terminals:  # EBNF dialects: NUM is a rule unless FR-14 is applied
            assert g.symbols["NUM"].kind is Kind.TERMINAL
        body = g.body("expr")
        shapes.add((len(body.options), tuple(type(i).__name__ for i in body.options[0].items)[::2]))
    assert len(shapes) == 1


def test_tc59_declared_nonterminal_without_rules(sqlite):
    # SQLite declares `%type part_opt` but never defines it.
    assert "declared, but has no rules" in build_page(sqlite, "part_opt")
    assert sqlite.used_by["part_opt"] == set()


@pytest.mark.parametrize("name", ["calc-bison.y", "c99.y", "sqlite-parse.y", "kukel.lark", "kukel.ebnf", "json-w3c.ebnf"])
def test_tc60_truncated_input_never_crashes(name):
    """NFR-2: every prefix of a real grammar either parses or raises GrammarError
    (regression for IndexError on input ending inside `[name]`)."""
    src = (FIX / name).read_text()
    reader = readers.choose(name, src)
    for n in range(0, len(src), max(1, len(src) // 300)):
        try:
            reader.read(src[:n], name)
        except GrammarError:
            pass
    with pytest.raises(GrammarError):
        yacc.read("%%\na [", "t.y")
