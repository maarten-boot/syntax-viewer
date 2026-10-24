"""Mutation fuzzing of all readers (NFR-2): any exception other than
GrammarError is a crash. Not collected by pytest; run manually:

    .venv/bin/python tests/fuzz_readers.py [iterations-per-fixture]
"""

import collections
import pathlib
import random
import sys
import traceback

from syntax_viewer import readers
from syntax_viewer.model import GrammarError

FIX = pathlib.Path(__file__).parent / "fixtures"
FIXTURES = {
    "kukel.ebnf": "ebnf-iso",
    "BBCBASIC.ebnf": "ebnf-iso",
    "json-w3c.ebnf": "ebnf-w3c",
    "kukel.lark": "lark",
    "calc-bison.y": "yacc",
    "c99.y": "yacc",
    "sqlite-parse.y": "lemon",
}
JUNK = list("{}()[]<>|;:.,=-*?!\"'%/\\\n ") + ["%%", "::=", "->", "/*", "*/", "(*", "*)", "..", "[A]", "%{", "%prec"]


def cases(src: str, n: int, rng: random.Random):
    yield from (src[:k] for k in range(0, len(src), max(1, len(src) // 400)))
    for _ in range(n):
        s = list(src)
        for _ in range(rng.randint(1, 4)):
            i = rng.randrange(len(s) + 1)
            if rng.random() < 0.5 and i < len(s):
                del s[i]
            else:
                s.insert(i, rng.choice(JUNK))
        yield "".join(s)


def main(n: int = 600) -> int:
    rng = random.Random(1)
    crashes = collections.defaultdict(list)
    for name, fmt in FIXTURES.items():
        reader = readers.get(fmt)
        for text in cases((FIX / name).read_text(), n, rng):
            try:
                reader.read(text, name)
            except (GrammarError, RecursionError):
                pass
            except Exception as exc:  # noqa: BLE001 - that is what we hunt for
                tb = traceback.extract_tb(exc.__traceback__)[-1]
                crashes[(fmt, type(exc).__name__, f"{pathlib.Path(tb.filename).name}:{tb.lineno}")].append(text)
    for key, texts in crashes.items():
        print(*key, len(texts))
    print(f"{len(crashes)} crash kinds")
    return 1 if crashes else 0


if __name__ == "__main__":
    sys.exit(main(*map(int, sys.argv[1:])))
