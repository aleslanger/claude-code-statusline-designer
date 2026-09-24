import pytest

from claude_style.config import CUSTOM_PRESET, set_color
from claude_style.palette import (
    BLACK,
    WHITE,
    contrast_fg,
    parse_color,
    to_hex,
    xterm_rgb,
)


def test_plain_code_is_accepted_as_is():
    assert parse_color("61") == 61


def test_hex_that_is_exactly_a_cube_color_maps_to_that_code():
    # 67 = 16 + 1*36 + 2*6 + 3 -> levels (95, 135, 175) = #5f87af
    assert parse_color("#5f87af") == 67
    assert to_hex(67) == "#5f87af"


def test_hex_without_hash_is_accepted():
    assert parse_color("5f87af") == 67


def test_hex_maps_to_the_nearest_code():
    code = parse_color("#5e81ac")  # Nord frost blue, not exactly on the cube

    r, g, b = xterm_rgb(code)
    assert abs(r - 0x5E) + abs(g - 0x81) + abs(b - 0xAC) < 30


@pytest.mark.parametrize("bad", ["256", "-1", "#12345", "blue", "#gggggg", ""])
def test_rejects_values_that_are_neither_code_nor_hex(bad):
    with pytest.raises(ValueError):
        parse_color(bad)


def test_grayscale_ramp_endpoints():
    assert xterm_rgb(232) == (8, 8, 8)
    assert xterm_rgb(255) == (238, 238, 238)


def test_contrast_picks_dark_text_on_light_and_light_text_on_dark():
    assert contrast_fg(231) == BLACK
    assert contrast_fg(16) == WHITE


def test_editing_a_color_marks_the_config_as_custom(config):
    set_color(config, "dir", "bg", 61)

    assert config["preset"] == CUSTOM_PRESET


def test_setting_the_same_color_keeps_the_scheme_name(config):
    set_color(config, "dir", "bg", config["segments"]["dir"]["bg"])

    assert config["preset"] == "agnoster"
