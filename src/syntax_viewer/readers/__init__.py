"""Reader plug-in interface and registry (FR-2, FR-4).

Built-in readers register themselves on import. Third-party readers can be
registered with `register()` or exposed through the `syntax_viewer.readers`
entry-point group (each entry point resolves to a Reader subclass).
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from importlib.metadata import entry_points

from syntax_viewer.model import Grammar, GrammarError


class Reader(ABC):
    name: str = ""
    extensions: tuple[str, ...] = ()

    def detect(self, path: str | None, text: str) -> float:
        """Confidence 0..1 that this reader handles the input.

        The default uses the extension only; readers sharing an extension
        (e.g. `.y`) override this to sniff the content.
        """
        if path and os.path.splitext(path)[1].lower() in self.extensions:
            return 0.5
        return 0.0

    @abstractmethod
    def read(self, text: str, path: str | None = None) -> Grammar:
        """Parse `text` into a finalized Grammar; raise GrammarError on bad input."""


_registry: dict[str, Reader] = {}
_plugins_loaded = False


def register(reader: Reader) -> Reader:
    _registry[reader.name] = reader
    return reader


def unregister(name: str) -> None:
    _registry.pop(name, None)


def _load_plugins() -> None:
    global _plugins_loaded
    if _plugins_loaded:
        return
    _plugins_loaded = True
    for ep in entry_points(group="syntax_viewer.readers"):
        register(ep.load()())


def readers() -> list[Reader]:
    _load_plugins()
    return list(_registry.values())


def get(name: str) -> Reader:
    _load_plugins()
    try:
        return _registry[name]
    except KeyError:
        known = ", ".join(sorted(_registry)) or "none"
        raise GrammarError(f"unknown format {name!r} (known: {known})") from None


def choose(path: str | None, text: str, override: str | None = None) -> Reader:
    """Pick the reader for the input; `override` forces a format by name."""
    if override:
        return get(override)
    scored = [(r.detect(path, text), r) for r in readers()]
    scored = [(score, r) for score, r in scored if score > 0]
    if not scored:
        raise GrammarError("cannot determine grammar format; use --format", path)
    return max(scored, key=lambda sr: sr[0])[1]


def load(path: str, override: str | None = None) -> Grammar:
    with open(path, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    try:
        return choose(path, text, override).read(text, path)
    except RecursionError:
        raise GrammarError("rules nested too deeply", path) from None


# Built-in readers register themselves on import.
from syntax_viewer.readers import iso_ebnf, lark, lemon, w3c_ebnf, yacc  # noqa: E402, F401
