"""Render the main window offscreen to PNG files for inspection without a
screen (used by `make screenshots`).

    python tools/screenshots.py OUTDIR [GRAMMAR SYMBOL [original]]...
"""

import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from syntax_viewer.gui import MainWindow  # noqa: E402

DEFAULT = [
    ("tests/fixtures/kukel.ebnf", "Identifier", False),
    ("tests/fixtures/BBCBASIC.ebnf", "type-suffix", True),
    ("tests/fixtures/kukel.lark", "statement", False),
    ("tests/fixtures/json-w3c.ebnf", "object", False),
    ("tests/fixtures/calc-bison.y", "exp", True),
    ("tests/fixtures/c99.y", "postfix_expression", False),
    ("tests/fixtures/sqlite-parse.y", "expr", False),
]


def main(outdir: str, *args: str) -> int:
    shots = DEFAULT
    if args:
        shots, rest = [], list(args)
        while rest:
            path, symbol = rest.pop(0), rest.pop(0)
            original = bool(rest) and rest[0] == "original" and bool(rest.pop(0))
            shots.append((path, symbol, original))
    os.makedirs(outdir, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    settings = QSettings(os.path.join(tempfile.mkdtemp(), "s.ini"), QSettings.Format.IniFormat)
    for path, symbol, original in shots:
        window = MainWindow(settings=settings, ask=lambda *a: True)
        window.resize(1200, 750)
        window.show()
        if not window.open(path) or not window.select(symbol):
            print(f"skipped {path} {symbol}", file=sys.stderr)
            continue
        window.act_original.setChecked(original)
        window._on_view_toggle(original)
        app.processEvents()
        name = f"{os.path.splitext(os.path.basename(path))[0]}-{symbol}{'-original' if original else ''}.png"
        window.grab().save(os.path.join(outdir, name))
        print(os.path.join(outdir, name))
        window.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
