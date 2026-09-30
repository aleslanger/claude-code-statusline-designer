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


def test_reinstall_replaces_the_script_atomically(claude_dir, config):
    # Regression: the script was rewritten in place, so Claude Code could run a
    # half-written file and show a blank or stale statusline until the next save.
    install(config)
    script = claude_dir / "statusline-command.sh"
    before = script.stat().st_ino
    with open(script, encoding="utf-8") as running:
        original = running.read()
        running.seek(0)

        install({**config, "labels": True})

        assert running.read() == original  # a run already in progress keeps reading a whole script
    assert script.stat().st_ino != before
    assert script.stat().st_mode & 0o777 == 0o755
    assert "model %s" in script.read_text()


def test_reinstall_rewrites_settings_so_claude_code_refreshes_right_away(claude_dir, config):
    # Claude Code re-runs the statusline when settings.json changes; an unchanged
    # file meant the running session kept the old look until the next event.
    install(config)
    settings = claude_dir / "settings.json"
    before = settings.stat().st_ino

    install(config)

    assert settings.stat().st_ino != before
    assert _settings(claude_dir)["statusLine"]["command"] == str(claude_dir / "statusline-command.sh")


def test_install_leaves_no_temporary_files_behind(claude_dir, config):
    install(config)
    install(config)

    assert sorted(p.name for p in claude_dir.iterdir()) == ["settings.json", "statusline-command.sh"]


def test_rewriting_settings_keeps_their_permissions(claude_dir, config):
    claude_dir.mkdir()
    settings = claude_dir / "settings.json"
    settings.write_text("{}")
    settings.chmod(0o644)

    install(config)

    assert settings.stat().st_mode & 0o777 == 0o644


def test_a_symlinked_settings_file_stays_a_symlink(claude_dir, config, tmp_path):
    # dotfile managers (stow, chezmoi symlink mode) link settings.json into ~/.claude
    claude_dir.mkdir()
    real = tmp_path / "dotfiles" / "settings.json"
    real.parent.mkdir()
    real.write_text(json.dumps({"model": "opus"}))
    (claude_dir / "settings.json").symlink_to(real)

    install(config)

    assert (claude_dir / "settings.json").is_symlink()
    assert json.loads(real.read_text())["statusLine"]["type"] == "command"
