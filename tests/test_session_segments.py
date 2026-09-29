import copy

import pytest

from claude_style.ansi import parse
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
    result = run_samples(config, [sample], columns=160)[0]
    assert result.error == ""
    return parse(result.output)


def _visible(config: dict, sample: dict) -> str:
    return "".join(run.text for run in _runs(config, sample))


def _sample(data: dict) -> dict:
    return {"label": "custom", "workdir": "projects/webapp", "data": {"session_id": "t", **data}}


def test_cache_shows_hit_ratio_and_time_until_it_goes_cold(config):
    assert "cache 87% (4m)" in _visible(_enabled(config, "cache"), CLEAN)


def test_cold_cache_is_labelled_and_colored_as_cold(config):
    cache = config["segments"]["cache"]

    runs = _runs(_enabled(config, "cache"), BUSY)
    segment = next(run for run in runs if "cache" in run.text)

    assert "cache 42% cold" in segment.text
    assert segment.style.bg == cache["colors"]["cold"]


def test_cache_is_hidden_before_the_first_response(config):
    assert "cache" not in _visible(_enabled(config, "cache"), FRESH)


def test_cache_can_hide_the_countdown(config):
    updated = _enabled(config, "cache")
    updated["segments"]["cache"]["show_ttl"] = False

    text = _visible(updated, CLEAN)

    assert "cache 87%" in text
    assert "(4m)" not in text


def test_session_name_is_shown(config):
    assert "fix login flow" in _visible(_enabled(config, "session"), CLEAN)


def test_long_session_name_is_shortened_with_an_ellipsis(config):
    assert "refactor payment webhoo…" in _visible(_enabled(config, "session"), BUSY)


def test_session_name_cannot_inject_terminal_escapes(config):
    sample = _sample({"session_name": "evil\u001b[31mname\u0007"})

    runs = _runs(_enabled(config, "session"), sample)

    assert "evil[31mname" in "".join(run.text for run in runs)


def test_mode_shows_fast_mode_vim_mode_and_agent(config):
    assert "fast NORMAL @reviewer" in _visible(_enabled(config, "mode"), BUSY)


def test_mode_is_hidden_when_nothing_is_active(config):
    assert "fast" not in _visible(_enabled(config, "mode"), CLEAN)


def test_mode_ignores_an_unknown_vim_mode(config):
    sample = _sample({"vim": {"mode": "$(id)"}, "fast_mode": True})

    text = _visible(_enabled(config, "mode"), sample)

    assert "fast" in text
    assert "$(id)" not in text


@pytest.mark.parametrize("length", [3, 201, "24", True])
def test_session_max_length_must_be_a_sane_integer(config, length):
    config["segments"]["session"]["max_length"] = length

    with pytest.raises(ConfigError, match="session.max_length"):
        validate_config(config)
