"""Shared test helpers: a tiny line-based reader used before real readers exist.

Format (one rule per line):   lhs : a 'b' | c ;     `%token NAME` declares a terminal.
"""

import re

import pytest

from syntax_viewer import readers
from syntax_viewer.model import Empty, Grammar, GrammarError, Literal, Rule, SourceSpan, SymRef, alt, seq


class DummyReader(readers.Reader):
    name = "dummy"
    extensions = (".dummy",)

    def read(self, text, path=None):
        g = Grammar(format=self.name, source=text, path=path)
        offset = 0
        for lineno, line in enumerate(text.splitlines(keepends=True), 1):
            stripped = line.strip()
            if stripped.startswith("%token"):
                for name in stripped.split()[1:]:
                    g.declare_terminal(name, declaration=stripped)
            elif stripped:
                m = re.fullmatch(r"(\w+)\s*:(.*);", stripped)
                if not m:
                    raise GrammarError("expected 'lhs : ... ;'", path, lineno)
                opts = []
                for part in m.group(2).split("|"):
                    items = [Literal(t) if t.startswith("'") else SymRef(t) for t in part.split()]
                    opts.append(seq(*items) if items else Empty())
                g.add_rule(Rule(m.group(1), alt(*opts), SourceSpan(offset, offset + len(line), lineno)))
            offset += len(line)
        return g.finalize()


@pytest.fixture
def dummy_reader():
    reader = readers.register(DummyReader())
    yield reader
    readers.unregister(reader.name)


CALC = """\
%token NUM UNUSED
expr : expr '+' term | term ;
term : NUM | '(' expr ')' ;
"""


@pytest.fixture
def calc(dummy_reader):
    return dummy_reader.read(CALC, "calc.dummy")
