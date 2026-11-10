import pytest

from docdrift import __version__
from docdrift.cli import main


def test_version_flag_prints_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_quiet_flag_prints_nothing(capsys):
    assert main(["--quiet"]) == 0
    assert capsys.readouterr().out == ""


def test_no_arguments_prints_help_and_exits_cleanly(capsys):
    assert main([]) == 0
    assert "usage: docdrift" in capsys.readouterr().out
