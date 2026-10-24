import subprocess
import sys

from syntax_viewer.cli import main


def test_tc24_dump(dummy_reader, tmp_path, capsys):
    f = tmp_path / "calc.dummy"
    f.write_text("%token NUM UNUSED\nexpr : expr '+' term | term ;\nterm : NUM ;\n")
    assert main(["--dump", str(f)]) == 0
    out = capsys.readouterr().out
    assert "expr ::= expr '+' term\n       | term" in out
    assert "UNUSED  [terminal]" in out and "(unused)" in out


def test_dump_error_exit_code(dummy_reader, tmp_path, capsys):
    f = tmp_path / "bad.dummy"
    f.write_text("oops\n")
    assert main(["--dump", str(f)]) == 1
    assert "bad.dummy:1:" in capsys.readouterr().err


def test_nfr1_core_does_not_import_qt():
    code = "import syntax_viewer.cli, syntax_viewer.readers, sys; print(any(m.startswith('PySide6') for m in sys.modules))"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout
    assert out.strip() == "False"


FIX = __import__("pathlib").Path(__file__).parent / "fixtures"


def test_tc24_dump_real_fixture(capsys):
    assert main(["--dump", str(FIX / "kukel.ebnf")]) == 0
    out = capsys.readouterr().out
    assert out.startswith("start ::= program")


def test_fr14_cli_flag(capsys):
    main(["--dump", str(FIX / "kukel.ebnf")])
    assert "Identifier  [terminal]" in capsys.readouterr().out  # auto: detected
    main(["--dump", "--uppercase-terminals", "no", str(FIX / "kukel.ebnf")])
    assert "Identifier ::=" in capsys.readouterr().out


def test_fr15_dump_shows_comments_for_lexical_terminals(capsys):
    main(["--dump", str(FIX / "kukel.ebnf")])
    block = capsys.readouterr().out.split("Identifier  [terminal]")[1].split("\n\n")[0]
    assert "trailing:" in block


def test_tc50_deep_nesting_is_an_error_not_a_crash(tmp_path, capsys):
    f = tmp_path / "deep.ebnf"
    f.write_text("a = " + "(" * 5000 + "b" + ")" * 5000 + " ;")
    assert main(["--dump", str(f)]) == 1
    assert "nested too deeply" in capsys.readouterr().err
