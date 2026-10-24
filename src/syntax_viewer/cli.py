"""Command-line entry point: `syntax-viewer [--dump] [--format NAME] FILE`."""

from __future__ import annotations

import argparse
import sys

from syntax_viewer import readers
from syntax_viewer.model import GrammarError, Kind
from syntax_viewer.render import expr_text, rule_text


def dump(grammar, out=None) -> None:
    """Headless dump: every symbol, its rule/definition and used-by (NFR-1)."""
    out = out or sys.stdout
    for sym in grammar.sorted_symbols():
        if sym.kind is Kind.NONTERMINAL and sym.name in grammar.rules:
            print(rule_text(grammar, sym.name), file=out)
        else:
            label = {Kind.NONTERMINAL: "rule", Kind.TERMINAL: "terminal", Kind.UNDEFINED: "UNDEFINED"}[sym.kind]
            print(f"{sym.name}  [{label}]", file=out)
            if sym.declaration:
                print(f"    declared: {sym.declaration}", file=out)
            if sym.definition is not None:
                print(f"    defined:  {expr_text(sym.definition)}", file=out)
        for rule in grammar.rules.get(sym.name, ()):
            for c in rule.comments:
                print(f"    {c.pos.value}: {' '.join(c.text.split())}", file=out)
        used = sorted(grammar.used_by.get(sym.name, ()))
        print(f"    used by:  {', '.join(used) if used else '(unused)'}", file=out)
        print(file=out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="syntax-viewer", description=__doc__)
    parser.add_argument("file", nargs="?", help="grammar file to open")
    parser.add_argument("--format", help="force a format (reader name)")
    parser.add_argument("--dump", action="store_true", help="print rules instead of opening the GUI")
    parser.add_argument(
        "--uppercase-terminals",
        choices=("auto", "yes", "no"),
        default="auto",
        help="treat upper-case rules as terminals (FR-14); auto = if the pattern is detected",
    )
    parser.add_argument("--list-formats", action="store_true", help="list known formats and exit")
    args = parser.parse_args(argv)

    if args.list_formats:
        for r in sorted(readers.readers(), key=lambda r: r.name):
            print(f"{r.name:12} {' '.join(r.extensions)}")
        return 0

    if args.dump:
        if not args.file:
            parser.error("--dump requires a file")
        try:
            grammar = readers.load(args.file, args.format)
        except (GrammarError, OSError) as exc:
            print(f"syntax-viewer: {exc}", file=sys.stderr)
            return 1
        if grammar.native_terminals:
            if args.uppercase_terminals == "yes":
                print(f"syntax-viewer: --uppercase-terminals ignored for {grammar.format}", file=sys.stderr)
        elif args.uppercase_terminals == "yes":
            grammar.set_lexical({n for n in grammar.rules if n[:1].isupper()})
        elif args.uppercase_terminals == "auto":
            grammar.set_lexical(grammar.lexical_candidates())
        dump(grammar)
        return 0

    try:
        from syntax_viewer.gui import run  # noqa: PLC0415 - GUI is optional
    except ImportError as exc:
        print(f"syntax-viewer: GUI not available ({exc}); use --dump", file=sys.stderr)
        return 2
    return run(args.file, args.format)
