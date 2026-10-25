"""Common grammar model shared by all readers (FR-5)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterator


class Kind(Enum):
    NONTERMINAL = "nonterminal"
    TERMINAL = "terminal"
    UNDEFINED = "undefined"  # referenced but never defined or declared


@dataclass(frozen=True)
class SourceSpan:
    """Half-open character range [start, end) in the source text, plus 1-based line."""

    start: int
    end: int
    line: int


# --- Rule body expressions -------------------------------------------------


class Expr:
    def children(self) -> tuple[Expr, ...]:
        return ()

    def walk(self) -> Iterator[Expr]:
        yield self
        for child in self.children():
            yield from child.walk()


@dataclass(frozen=True)
class Empty(Expr):
    """The empty alternative (epsilon)."""


@dataclass(frozen=True)
class SymRef(Expr):
    """Reference to a named symbol (non-terminal or named terminal)."""

    name: str


@dataclass(frozen=True)
class Literal(Expr):
    """Quoted literal; `text` keeps the quotes as written, e.g. "'+'"."""

    text: str


@dataclass(frozen=True)
class Regex(Expr):
    """Regular-expression terminal, `pattern` as written incl. delimiters."""

    pattern: str


@dataclass(frozen=True)
class Seq(Expr):
    items: tuple[Expr, ...]

    def children(self) -> tuple[Expr, ...]:
        return self.items


@dataclass(frozen=True)
class Alt(Expr):
    options: tuple[Expr, ...]

    def children(self) -> tuple[Expr, ...]:
        return self.options


@dataclass(frozen=True)
class Opt(Expr):
    expr: Expr

    def children(self) -> tuple[Expr, ...]:
        return (self.expr,)


@dataclass(frozen=True)
class Star(Expr):
    expr: Expr

    def children(self) -> tuple[Expr, ...]:
        return (self.expr,)


@dataclass(frozen=True)
class Plus(Expr):
    expr: Expr

    def children(self) -> tuple[Expr, ...]:
        return (self.expr,)


@dataclass(frozen=True)
class Except(Expr):
    """ISO 14977 exception `base - exclude`."""

    base: Expr
    exclude: Expr

    def children(self) -> tuple[Expr, ...]:
        return (self.base, self.exclude)


@dataclass(frozen=True)
class Repeat(Expr):
    """Fixed repetition: ISO `count * expr`, Lark `expr ~ count[..high]`."""

    count: int
    expr: Expr
    high: int | None = None

    def children(self) -> tuple[Expr, ...]:
        return (self.expr,)


@dataclass(frozen=True)
class Range(Expr):
    """Character range `"a" .. "z"`; bounds keep their quotes."""

    low: str
    high: str

    @property
    def text(self) -> str:
        return f"{self.low} .. {self.high}"


@dataclass(frozen=True)
class Special(Expr):
    """ISO 14977 special sequence `? free text ?`, kept as written."""

    text: str


@dataclass(frozen=True)
class Param(Expr):
    """Template parameter inside a template body (Lark `name{x}`): a local
    placeholder, not a symbol."""

    name: str


@dataclass(frozen=True)
class Call(Expr):
    """Use of a template (Lark `name{arg, ...}`): references `name` and its args."""

    name: str
    args: tuple[Expr, ...]

    def children(self) -> tuple[Expr, ...]:
        return self.args


def seq(*items: Expr) -> Expr:
    """Build a sequence, collapsing trivial cases."""
    if not items:
        return Empty()
    if len(items) == 1:
        return items[0]
    return Seq(tuple(items))


def alt(*options: Expr) -> Expr:
    """Build an alternation, collapsing the single-option case."""
    if len(options) == 1:
        return options[0]
    return Alt(tuple(options))


def alternatives(expr: Expr) -> tuple[Expr, ...]:
    """Top-level alternatives of a rule body."""
    return expr.options if isinstance(expr, Alt) else (expr,)


def symbol_name(expr: Expr) -> str | None:
    """Name under which a leaf expression appears in the symbol list."""
    if isinstance(expr, (SymRef, Call)):
        return expr.name
    if isinstance(expr, Literal):
        return expr.text
    if isinstance(expr, Regex):
        return expr.pattern
    if isinstance(expr, (Range, Special)):
        return expr.text
    return None


# --- Grammar ---------------------------------------------------------------


class CommentPos(Enum):
    LEADING = "leading"
    INNER = "inner"
    TRAILING = "trailing"


@dataclass
class Comment:
    text: str  # as written, including delimiters
    span: SourceSpan
    pos: CommentPos | None = None


@dataclass
class Rule:
    """One rule as written in the source. A non-terminal may have several
    (Yacc `a: x; a: y;`, Lemon one rule per production)."""

    lhs: str
    body: Expr
    span: SourceSpan | None = None
    comments: list[Comment] = field(default_factory=list)  # FR-15
    params: tuple[str, ...] = ()  # template parameters (Lark `name{a, b}: ...`)
    # Source ranges inside `span` left out of the original view (Yacc actions, FR-11).
    elided: list[SourceSpan] = field(default_factory=list)


@dataclass
class Symbol:
    name: str
    kind: Kind
    # Terminal definition (Lark pattern, ...) if the format has one.
    definition: Expr | None = None
    # Declaration text, e.g. "%token <num> NUMBER", if any.
    declaration: str | None = None
    span: SourceSpan | None = None


@dataclass
class Grammar:
    format: str = ""
    source: str = ""
    path: str | None = None
    start: str | None = None
    rules: dict[str, list[Rule]] = field(default_factory=dict)
    symbols: dict[str, Symbol] = field(default_factory=dict)
    used_by: dict[str, set[str]] = field(default_factory=dict)
    # Rules shown as terminals by the uppercase-lexical convention (FR-14).
    lexical: set[str] = field(default_factory=set)
    # True for formats with their own terminal syntax (Lark); FR-14 then never applies.
    native_terminals: bool = False

    # -- building (used by readers) --

    def add_rule(self, rule: Rule) -> None:
        self.rules.setdefault(rule.lhs, []).append(rule)
        if self.start is None:
            self.start = rule.lhs

    def declare_terminal(
        self,
        name: str,
        definition: Expr | None = None,
        declaration: str | None = None,
        span: SourceSpan | None = None,
    ) -> None:
        sym = self.symbols.get(name)
        if sym is None:
            self.symbols[name] = Symbol(name, Kind.TERMINAL, definition, declaration, span)
            return
        sym.definition = definition or sym.definition
        sym.declaration = declaration or sym.declaration
        sym.span = span or sym.span

    def finalize(self) -> Grammar:
        """Classify every symbol and build the used-by index (FR-6, FR-12)."""
        for name, rules in self.rules.items():
            sym = self.symbols.get(name)
            if sym is None:
                self.symbols[name] = Symbol(name, Kind.NONTERMINAL, span=rules[0].span)
            else:
                sym.kind = Kind.NONTERMINAL
                sym.span = sym.span or rules[0].span
        self.set_lexical(self.lexical)

        self.used_by = {name: set() for name in self.symbols}
        for lhs, rules in self.rules.items():
            for rule in rules:
                for node in rule.body.walk():
                    name = symbol_name(node)
                    if name is None:
                        continue
                    if name not in self.symbols:
                        kind = Kind.UNDEFINED if isinstance(node, (SymRef, Call)) else Kind.TERMINAL
                        self.symbols[name] = Symbol(name, kind)
                    self.used_by.setdefault(name, set()).add(lhs)
        return self

    def lexical_candidates(self) -> set[str]:
        """Rules that look lexical by the uppercase convention (FR-14): both
        upper- and lower-case rule names exist and no upper-case rule refers
        to a lower-case one. Empty if the pattern is absent."""
        if self.native_terminals:
            return set()
        upper = {n for n in self.rules if n[:1].isupper()}
        lower = set(self.rules) - upper
        if not upper or not lower:
            return set()
        for name in upper:
            for rule in self.rules[name]:
                for node in rule.body.walk():
                    if isinstance(node, SymRef) and node.name in lower:
                        return set()
        return upper

    def set_lexical(self, names: set[str]) -> None:
        """Show the given rules as terminals (definition = rule body), and
        every other rule as a non-terminal. Can be changed at any time."""
        self.lexical = set(names) & set(self.rules)
        for name in self.rules:
            sym = self.symbols[name]
            if name in self.lexical:
                sym.kind = Kind.TERMINAL
                sym.definition = self.body(name)
            elif sym.kind is Kind.TERMINAL and sym.definition == self.body(name):
                sym.kind = Kind.NONTERMINAL
                sym.definition = None

    # -- querying --

    def body(self, name: str) -> Expr | None:
        """All alternatives of a non-terminal merged into one expression."""
        rules = self.rules.get(name)
        if not rules:
            return None
        opts: list[Expr] = []
        for rule in rules:
            opts.extend(alternatives(rule.body))
        return alt(*opts)

    def sorted_symbols(self) -> list[Symbol]:
        """Non-terminals first (start symbol leading), then terminals (named
        ones before literals, regexes, ...), then undefined (FR-6)."""
        order = {Kind.NONTERMINAL: 0, Kind.TERMINAL: 1, Kind.UNDEFINED: 2}
        return sorted(
            self.symbols.values(),
            key=lambda s: (order[s.kind], s.name != self.start, not _NAMED.fullmatch(s.name), s.name.lower(), s.name),
        )


_NAMED = re.compile(r"[A-Za-z_][\w.-]*")
_BLANK_LINE = re.compile(r"\n[ \t\r]*\n")


def attach_comments(source: str, rules: list[Rule], comments: list[Comment]) -> None:
    """Attach comments to rules by position (FR-15).

    Inner: inside a rule's span. Trailing: after a rule with no blank line in
    between (consecutive trailing comments chain). Leading: directly above a
    rule with no blank line in between. When both trailing and leading fit,
    an indented or same-line comment is trailing, otherwise leading. Anything
    else (section headers) stays unattached.
    """
    ordered = sorted((r for r in rules if r.span), key=lambda r: r.span.start)
    if not ordered:
        return

    def no_blank_line(a: int, b: int) -> bool:
        return _BLANK_LINE.search(source, a, b) is None

    anchor: tuple[Rule, int] | None = None  # rule taking trailing comments, end offset
    ri = 0
    for c in sorted(comments, key=lambda c: c.span.start):
        while ri < len(ordered) and ordered[ri].span.end <= c.span.start:
            anchor = (ordered[ri], ordered[ri].span.end)
            ri += 1
        nxt = ordered[ri] if ri < len(ordered) else None
        if nxt and nxt.span.start <= c.span.start:
            c.pos = CommentPos.INNER
            nxt.comments.append(c)
            continue
        trailing_ok = anchor is not None and no_blank_line(anchor[1], c.span.start)
        leading_ok = nxt is not None and no_blank_line(c.span.end, nxt.span.start)
        if trailing_ok and leading_ok:
            line_start = source.rfind("\n", 0, c.span.start) + 1
            prefix = source[line_start : c.span.start]
            trailing_ok = prefix != "" or anchor[0].span.end > line_start
            leading_ok = not trailing_ok
        if trailing_ok:
            c.pos = CommentPos.TRAILING
            anchor[0].comments.append(c)
            anchor = (anchor[0], c.span.end)
        elif leading_ok:
            c.pos = CommentPos.LEADING
            nxt.comments.append(c)
        else:
            anchor = None


class GrammarError(Exception):
    """Malformed grammar input (NFR-2)."""

    def __init__(self, message: str, path: str | None = None, line: int | None = None):
        self.message = message
        self.path = path
        self.line = line
        where = f"{path or '<input>'}:{line}" if line is not None else (path or "<input>")
        super().__init__(f"{where}: {message}")
