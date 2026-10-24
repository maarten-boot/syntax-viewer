from syntax_viewer.model import Alt, Grammar, Kind, Literal, Opt, Plus, Rule, Seq, Star, SymRef
from syntax_viewer.render import expr_text, rule_text


def test_tc14_ebnf_operators_render():
    # a ::= b? c* (d | e)+
    body = Seq((Opt(SymRef("b")), Star(SymRef("c")), Plus(Alt((SymRef("d"), SymRef("e"))))))
    assert expr_text(body) == "b? c* ( d | e )+"


def test_symbol_kinds(calc):
    k = {n: s.kind for n, s in calc.symbols.items()}
    assert k["expr"] is k["term"] is Kind.NONTERMINAL
    assert k["NUM"] is k["'+'"] is Kind.TERMINAL
    assert calc.start == "expr"


def test_tc16_undefined_symbol():
    g = Grammar()
    g.add_rule(Rule("a", SymRef("foo")))
    g.finalize()
    assert g.symbols["foo"].kind is Kind.UNDEFINED


def test_tc30_used_by_nonterminal(calc):
    assert calc.used_by["term"] == {"expr"}


def test_tc31_used_by_terminal_and_self(calc):
    assert calc.used_by["'+'"] == {"expr"}
    assert calc.used_by["expr"] == {"expr", "term"}


def test_tc32_unused(calc):
    assert calc.used_by["UNUSED"] == set()


def test_multiple_rules_same_lhs_merge():
    g = Grammar()
    g.add_rule(Rule("a", SymRef("x")))
    g.add_rule(Rule("a", Alt((SymRef("y"), Literal("'z'")))))
    g.finalize()
    assert rule_text(g, "a") == "a ::= x\n    | y\n    | 'z'"


def test_sorted_symbols_order(calc):
    names = [s.name for s in calc.sorted_symbols()]
    assert names[0] == "expr"  # start symbol first
    assert names.index("term") < names.index("NUM")


def test_tc54_named_terminals_before_literals(calc):
    names = [s.name for s in calc.sorted_symbols()]
    assert names.index("NUM") < names.index("'+'")
