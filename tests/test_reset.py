import pytest

from claude_style.config import CUSTOM_PRESET, get_color, set_color
from claude_style.reset import (
    base_config,
    base_scheme_name,
    is_modified,
    modified_fields,
    reset_fields,
)
from claude_style.schemes import SchemeError, delete_scheme, save_scheme, scheme_config


def test_editing_a_color_remembers_which_scheme_it_came_from():
    config = scheme_config("nord")

    set_color(config, "dir", "bg", 200)

    assert config["preset"] == CUSTOM_PRESET
    assert base_scheme_name(config) == "nord"


def test_further_edits_keep_the_original_base():
    config = scheme_config("nord")
    set_color(config, "dir", "bg", 200)
    set_color(config, "git", "fg", 201)

    assert base_scheme_name(config) == "nord"


def test_modified_fields_lists_only_changed_colors():
    config = scheme_config("dracula")
    set_color(config, "effort", "colors.max", 196)

    assert modified_fields(config, base_config(config), "effort") == {"colors.max"}
    assert modified_fields(config, base_config(config), "dir") == set()


def test_resetting_one_field_restores_its_scheme_value():
    config = scheme_config("gruvbox")
    original = get_color(config, "dir", "bg")
    set_color(config, "dir", "bg", 200)
    set_color(config, "dir", "fg", 201)

    reset_fields(config, "dir", ["bg"])

    assert get_color(config, "dir", "bg") == original
    assert get_color(config, "dir", "fg") == 201
    assert config["preset"] == CUSTOM_PRESET


def test_resetting_the_last_change_brings_the_scheme_name_back():
    config = scheme_config("gruvbox")
    set_color(config, "dir", "bg", 200)

    reset_fields(config, "dir", ["bg"])

    assert config["preset"] == "gruvbox"
    assert config["based_on"] is None
    assert not is_modified(config, base_config(config))


def test_toggled_segment_counts_as_a_change_to_reset():
    config = scheme_config("agnoster")
    config["segments"]["git"]["enabled"] = False

    assert is_modified(config, base_config(config))
    assert base_config(config)["segments"]["git"]["enabled"] is True


def test_reset_explains_when_the_base_scheme_was_deleted(schemes_dir):
    save_scheme("temp", scheme_config("nord"))
    config = scheme_config("temp")
    set_color(config, "dir", "bg", 200)
    delete_scheme("temp")

    with pytest.raises(SchemeError, match="no longer exists"):
        reset_fields(config, "dir", ["bg"])


def test_custom_config_without_base_has_nothing_to_reset_to(config):
    config["preset"], config["based_on"] = CUSTOM_PRESET, None

    with pytest.raises(SchemeError, match="nothing to reset"):
        base_config(config)


def test_saved_and_exported_schemes_do_not_carry_based_on(schemes_dir):
    config = scheme_config("nord")
    set_color(config, "dir", "bg", 200)

    save_scheme("mine", config)

    assert scheme_config("mine")["based_on"] is None
