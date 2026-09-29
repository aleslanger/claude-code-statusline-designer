import copy

import pytest

from claude_style.ansi import parse
from claude_style.config import DEFAULT_CONFIG, SEGMENT_ORDER
from claude_style.glyphs import GLYPH_MODES
from claude_style.preset_builders import usage_extras
from claude_style.preview import SAMPLES, run_samples
from claude_style.validate import ConfigError, validate_config

CLEAN, BUSY, FRESH = SAMPLES


def _enabled(config: dict, *segments: str, glyphs: str = "unicode") -> dict:
    updated = copy.deepcopy(config)
    updated["glyphs"] = glyphs
    for segment in segments:
        updated["segments"][segment]["enabled"] = True
    return updated


def _runs(config: dict, sample: dict) -> list:
    result = run_samples(config, [sample], columns=120)[0]
    assert result.error == ""
    return parse(result.output)


def _visible(config: dict, sample: dict) -> str:
    return "".join(run.text for run in _runs(config, sample))


def _sample(data: dict, **extra) -> dict:
    return {"label": "custom", "workdir": "projects/webapp", "data": {"session_id": "t", **data}, **extra}


def test_limits_show_five_hour_and_weekly_usage_with_time_to_reset(config):
    text = _visible(_enabled(config, "limits"), CLEAN)

    assert "5h 23% (2h14m)" in text
    assert "7d 41% (3d4h)" in text


def test_limits_turn_critical_past_the_upper_threshold(config):
    limits = config["segments"]["limits"]

    runs = _runs(_enabled(config, "limits"), BUSY)
    five_hour = next(run for run in runs if "5h" in run.text)

    assert five_hour.style.bg == limits["colors"]["crit"]


def test_limits_are_hidden_without_rate_limit_data(config):
    assert "5h" not in _visible(_enabled(config, "limits"), FRESH)


def test_limits_show_the_gateway_spend_limit_when_present(config):
    sample = _sample({"rate_limits": {"spend_limit": {"used_percentage": 104.4}}})

    assert "spend 104%" in _visible(_enabled(config, "limits"), sample)


def test_limits_can_hide_the_reset_countdown(config):
    updated = _enabled(config, "limits")
    updated["segments"]["limits"]["show_reset"] = False

    text = _visible(updated, CLEAN)

    assert "5h 23% " in text
    assert "(2h14m)" not in text


def test_limits_ignore_values_that_are_not_numbers(config):
    sample = _sample({"rate_limits": {"five_hour": {"used_percentage": "$(echo pwned)", "resets_at": "a[$(id)]"}}})

    text = _visible(_enabled(config, "limits"), sample)

    assert "5h" not in text
    assert "pwned" not in text


def test_lines_show_added_and_removed_counts(config):
    assert "+156 -23" in _visible(_enabled(config, "lines"), CLEAN)


def test_lines_are_hidden_while_nothing_changed(config):
    assert "+0" not in _visible(_enabled(config, "lines"), FRESH)


def test_pr_shows_number_and_review_state(config):
    assert "#42 ✗" in _visible(_enabled(config, "pr"), BUSY)


def test_pr_uses_the_gitlab_merge_request_prefix(config):
    sample = _sample({"pr": {"number": 7, "kind": "mr", "review_state": "approved"}})

    assert "!7 ✓" in _visible(_enabled(config, "pr"), sample)


def test_pr_state_glyphs_are_ascii_in_ascii_mode(config):
    text = _visible(_enabled(config, "pr", glyphs="ascii"), BUSY)

    assert "#42 x" in text
    assert text.isascii()


def test_pr_is_hidden_without_an_open_pull_request(config):
    assert "#" not in _visible(_enabled(config, "pr"), CLEAN)


@pytest.mark.parametrize("thresholds", [[90, 70], [50, 50], [0, 90], [70, 101], [70], "70,90"])
def test_limit_thresholds_must_be_two_ascending_percentages(config, thresholds):
    config["segments"]["limits"]["thresholds"] = thresholds

    with pytest.raises(ConfigError, match="limits.thresholds"):
        validate_config(config)


def test_default_theme_borrows_usage_colors_like_every_other_theme():
    segments = DEFAULT_CONFIG["segments"]

    for segment, colors in usage_extras(segments).items():
        assert {key: segments[segment][key] for key in colors} == colors, segment


@pytest.mark.parametrize("separator", ["powerline", "plain"])
@pytest.mark.parametrize("glyphs", GLYPH_MODES)
def test_every_segment_at_once_renders_cleanly(config, separator, glyphs):
    updated = _enabled(config, *SEGMENT_ORDER, glyphs=glyphs)
    updated["separator"] = separator

    results = run_samples(updated, columns=120)

    assert [r.error for r in results] == [""] * len(SAMPLES)
