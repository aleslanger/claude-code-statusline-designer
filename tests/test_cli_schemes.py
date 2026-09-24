import io
import json

import pytest

from claude_style import config as config_module
from claude_style.cli import EXIT_ERROR, EXIT_OK, main
from claude_style.schemes import scheme_config


@pytest.fixture
def home(tmp_path, monkeypatch, schemes_dir):
    config_dir = tmp_path / "cfg"
    monkeypatch.setattr(config_module, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config_module, "CONFIG_PATH", config_dir / "config.json")
    return tmp_path


def _current_config():
    return config_module.load_config()


def test_color_set_accepts_hex_and_marks_config_custom(home, capsys):
    assert main(["color", "set", "dir", "bg", "#5f87af"]) == EXIT_OK

    assert _current_config()["segments"]["dir"]["bg"] == 67
    assert _current_config()["preset"] == "custom"
    assert "#5f87af" in capsys.readouterr().out


def test_color_set_rejects_garbage_with_exit_code_1(home, capsys):
    assert main(["color", "set", "dir", "bg", "blue"]) == EXIT_ERROR
    assert "error:" in capsys.readouterr().err


def test_save_list_export_import_apply_delete_flow(home, capsys):
    main(["color", "set", "model", "bg", "201"])
    assert main(["scheme", "save", "pink"]) == EXIT_OK
    assert _current_config()["preset"] == "pink"

    main(["scheme", "list"])
    assert "pink" in capsys.readouterr().out

    exported = home / "pink.json"
    assert main(["scheme", "export", "pink", "-o", str(exported)]) == EXIT_OK
    assert json.loads(exported.read_text())["config"]["segments"]["model"]["bg"] == 201

    main(["preset", "agnoster"])
    assert main(["scheme", "import", str(exported), "--name", "pink-copy", "--apply"]) == EXIT_OK
    assert _current_config()["preset"] == "pink-copy"
    assert _current_config()["segments"]["model"]["bg"] == 201

    assert main(["scheme", "delete", "pink-copy"]) == EXIT_OK
    assert _current_config()["preset"] == "custom"


def test_export_to_existing_file_needs_overwrite(home):
    target = home / "out.json"
    target.write_text("keep me")

    assert main(["scheme", "export", "nord", "-o", str(target)]) == EXIT_ERROR
    assert target.read_text() == "keep me"
    assert main(["scheme", "export", "nord", "-o", str(target), "--overwrite"]) == EXIT_OK


def test_export_without_output_prints_scheme_json(home, capsys):
    main(["scheme", "export", "gruvbox"])

    assert json.loads(capsys.readouterr().out)["name"] == "gruvbox"


def test_import_from_stdin(home, monkeypatch, capsys):
    main(["scheme", "export", "dracula"])
    exported = capsys.readouterr().out.replace('"name": "dracula"', '"name": "drac2"')
    monkeypatch.setattr("sys.stdin", io.StringIO(exported))

    assert main(["scheme", "import", "-"]) == EXIT_OK
    assert "drac2" in capsys.readouterr().out


def test_malicious_import_fails_cleanly(home, capsys):
    main(["scheme", "export", "nord"])
    doc = json.loads(capsys.readouterr().out)
    doc["name"] = "evil"
    doc["config"]["separator"] = "powerline; rm -rf ~"
    evil = home / "evil.json"
    evil.write_text(json.dumps(doc))

    assert main(["scheme", "import", str(evil)]) == EXIT_ERROR
    assert "separator" in capsys.readouterr().err
    assert main(["preset", "evil"]) == EXIT_ERROR


def test_color_reset_one_field_and_whole_reset(home):
    nord_dir = scheme_config("nord")["segments"]["dir"]
    main(["preset", "nord"])
    main(["color", "set", "dir", "bg", "200"])
    main(["color", "set", "dir", "fg", "201"])

    assert main(["color", "reset", "dir", "bg"]) == EXIT_OK
    assert _current_config()["segments"]["dir"]["bg"] == nord_dir["bg"]
    assert _current_config()["segments"]["dir"]["fg"] == 201

    assert main(["reset"]) == EXIT_OK
    assert _current_config()["preset"] == "nord"
    assert _current_config()["segments"]["dir"]["fg"] == nord_dir["fg"]


def test_color_reset_rejects_unknown_field(home, capsys):
    assert main(["color", "reset", "dir", "nope"]) == EXIT_ERROR
    assert "unknown field" in capsys.readouterr().err


def test_unknown_preset_lists_what_is_available(home, capsys):
    assert main(["preset", "nope"]) == EXIT_ERROR
    assert "agnoster" in capsys.readouterr().err
