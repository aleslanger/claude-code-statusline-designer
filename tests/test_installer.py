import json

import pytest

from claude_style import installer
from claude_style.cli import EXIT_ERROR, main
from claude_style.installer import InstallError, install, uninstall

USER_SCRIPT = "#!/bin/sh\necho my own statusline\n"


@pytest.fixture
def claude_dir(tmp_path, monkeypatch):
    target = tmp_path / ".claude"
    monkeypatch.setattr(installer, "CLAUDE_DIR", target)
    monkeypatch.setattr(installer, "STATUSLINE_PATH", target / "statusline-command.sh")
    monkeypatch.setattr(installer, "SETTINGS_PATH", target / "settings.json")
    return target


def _settings(claude_dir):
    return json.loads((claude_dir / "settings.json").read_text())


def test_install_works_before_claude_code_ever_ran(claude_dir, config):
    # Regression: ~/.claude missing -> FileNotFoundError traceback.
    install(config)

    assert (claude_dir / "statusline-command.sh").stat().st_mode & 0o111
    assert _settings(claude_dir)["statusLine"]["command"] == str(claude_dir / "statusline-command.sh")


def test_install_creates_settings_json_when_missing(claude_dir, config):
    # Regression: a missing settings.json was skipped silently, so "installed"
    # was reported but Claude Code never ran the statusline.
    claude_dir.mkdir()

    install(config)

    assert "statusLine" in _settings(claude_dir)


def test_install_keeps_other_settings(claude_dir, config):
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text(json.dumps({"model": "opus", "permissions": {"allow": ["Bash"]}}))

    install(config)

    settings = _settings(claude_dir)
    assert settings["model"] == "opus"
    assert settings["permissions"] == {"allow": ["Bash"]}


def test_broken_settings_json_is_reported_and_left_untouched(claude_dir, config):
    claude_dir.mkdir()
    broken = '{"model": "opus",'
    (claude_dir / "settings.json").write_text(broken)

    with pytest.raises(InstallError, match="not valid JSON"):
        install(config)

    assert (claude_dir / "settings.json").read_text() == broken
    assert not (claude_dir / "statusline-command.sh").exists()


def test_reinstalling_never_overwrites_the_users_original_backup(claude_dir, config):
    # Regression: every install copied the current script to .bak, so the
    # second install replaced the user's original with a generated script.
    claude_dir.mkdir()
    (claude_dir / "statusline-command.sh").write_text(USER_SCRIPT)

    install(config)
    install(config)

    assert (claude_dir / "statusline-command.sh.bak").read_text() == USER_SCRIPT


def test_uninstall_restores_the_original_and_drops_the_key(claude_dir, config):
    claude_dir.mkdir()
    (claude_dir / "statusline-command.sh").write_text(USER_SCRIPT)
    install(config)
    install(config)

    assert uninstall() is True
    assert (claude_dir / "statusline-command.sh").read_text() == USER_SCRIPT
    assert "statusLine" not in _settings(claude_dir)


def test_cli_reports_install_errors_without_a_traceback(claude_dir, capsys, monkeypatch, tmp_path):
    from claude_style import config as config_module

    monkeypatch.setattr(config_module, "CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr(config_module, "CONFIG_PATH", tmp_path / "cfg" / "config.json")
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text("[1, 2")

    assert main(["install"]) == EXIT_ERROR
    assert "not valid JSON" in capsys.readouterr().err
