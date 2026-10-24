import pytest

from syntax_viewer import readers
from syntax_viewer.model import GrammarError


def test_tc12_plugin_registration(dummy_reader):
    assert readers.choose("x.dummy", "") is dummy_reader
    assert dummy_reader in readers.readers()


def test_tc05_format_override(dummy_reader):
    assert readers.choose("grammar.txt", "", override="dummy") is dummy_reader


def test_unknown_format_errors():
    with pytest.raises(GrammarError, match="cannot determine"):
        readers.choose("grammar.unknownext", "")
    with pytest.raises(GrammarError, match="unknown format"):
        readers.get("nope")


def test_tc11_error_has_file_and_line(dummy_reader):
    with pytest.raises(GrammarError) as exc:
        dummy_reader.read("a : b ;\nbroken\n", "bad.dummy")
    assert exc.value.line == 2
    assert str(exc.value).startswith("bad.dummy:2:")


def test_tc12_entry_point_plugins(monkeypatch):
    """FR-4: readers exposed through the `syntax_viewer.readers` entry-point group load."""
    from conftest import DummyReader

    class EP:
        def load(self):
            return DummyReader

    monkeypatch.setattr(readers, "_plugins_loaded", False)
    monkeypatch.setattr(readers, "entry_points", lambda group: [EP()] if group == "syntax_viewer.readers" else [])
    try:
        assert readers.get("dummy").name == "dummy"
    finally:
        readers.unregister("dummy")
