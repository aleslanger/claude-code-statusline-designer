"""Row layout of the generated statusline: dividers between equal colors, wrapping and labels."""
import copy
import re

import pytest

from claude_style import config as config_module
from claude_style.ansi import parse
from claude_style.cli import EXIT_OK, main
from claude_style.glyphs import GLYPH_MODES
from claude_style.preview import SAMPLES, run_samples
from claude_style.render_layout import WRAP_MARGIN
from claude_style.validate import ConfigError, validate_config

CLEAN, BUSY, FRESH = SAMPLES
ARROW = "▌"  # the unicode glyph set's segment edge
THIN = "│"
WIDE = 400
NARROW = 80
SGR_RE = re.compile(r"\x1b\[[0-9;]*m")


def _with(config: dict, *segments: str, **options) -> dict:
    updated = copy.deepcopy(config)
    updated["glyphs"] = "unicode"
    for segment in segments:
        updated["segments"][segment]["enabled"] = True
    updated.update(options)
    return updated


def _all_segments(config: dict, **options) -> dict:
    return _with(config, *config["segments"], **options)


def _output(config: dict, sample: dict, columns: int = WIDE) -> str:
    result = run_samples(config, [sample], columns=columns)[0]
    assert result.error == ""
    return result.output


def _visible(config: dict, sample: dict, columns: int = WIDE) -> str:
    return "".join(run.text for run in parse(_output(config, sample, columns)))


def _sample(data: dict) -> dict:
    return {"label": "custom", "workdir": "projects/webapp", "data": {"session_id": "t", **data}}


def test_equal_neighbouring_backgrounds_get_a_thin_divider_instead_of_an_invisible_arrow(config):
    # In CLEAN both limit windows are under the warn threshold, so both use the "ok" background.
    text = _visible(_with(config, "limits"), CLEAN)

    assert f"5h 23% (2h14m) {THIN} 7d 41%" in text


def test_different_neighbouring_backgrounds_keep_the_arrow(config):
    # BUSY: the 5h window is critical, the weekly one only warns.
    text = _visible(_with(config, "limits"), BUSY)

    assert f"5h 92% (38m) {ARROW} 7d 78%" in text


def test_without_true_color_a_red_context_next_to_a_red_limit_gets_a_thin_divider(config, monkeypatch):
    # Regression (CI has no COLORTERM): at 90% the context uses its red threshold
    # background, the same red as a critical limit right after it.
    monkeypatch.delenv("COLORTERM", raising=False)

    text = _visible(_with(config, "limits"), BUSY)

    assert f"90% {THIN} 5h 92%" in text


def test_thin_divider_is_drawn_in_the_text_color_of_the_segment_before_it(config):
    updated = _with(config, "limits")

    runs = parse(_output(updated, CLEAN))
    divider = next(run for run in runs if THIN in run.text)

    assert divider.style.fg == updated["segments"]["limits"]["fg"]
    assert divider.style.bg == updated["segments"]["limits"]["colors"]["ok"]


@pytest.mark.parametrize("separator", ["powerline", "plain"])
def test_a_line_too_wide_for_the_terminal_wraps_onto_more_rows(config, separator):
    updated = _all_segments(config, separator=separator)

    rows = _output(updated, BUSY, NARROW).split("\n")

    assert len(rows) >= 2
    for row in rows:
        assert len(SGR_RE.sub("", row)) <= NARROW - WRAP_MARGIN


@pytest.mark.parametrize("separator", ["powerline", "plain"])
def test_wrapping_breaks_only_between_segments(config, separator):
    updated = _all_segments(config, separator=separator)

    wrapped = _visible(updated, BUSY, NARROW)
    one_row = _visible(updated, BUSY)

    for piece in ("feature/login", "refactor payment", "think on", "7d 78% (1d9h)", "+1204 -387", "1h35m"):
        assert piece in one_row
        assert piece in wrapped


def test_every_wrapped_powerline_row_is_closed_and_starts_on_its_own_background(config):
    updated = _all_segments(config)

    rows = _output(updated, BUSY, NARROW).split("\n")

    for row in rows:
        assert row.endswith("\x1b[0m")
        assert row.startswith("\x1b[48;")  # background first, no leftover edge from the row above


def test_a_line_that_fits_stays_on_one_row(config):
    assert "\n" not in _output(_all_segments(config), BUSY, WIDE)


def test_wrapping_can_be_turned_off(config):
    updated = _all_segments(config, wrap=False)

    assert "\n" not in _output(updated, BUSY, NARROW)


def test_labels_name_each_value(config):
    updated = _all_segments(config, labels=True)

    text = _visible(updated, BUSY)

    for labelled in ("model Opus 5", "effort max", "ctx ", "limit 5h 92%", "cost $7.80", "time 1h35m", "lines +1204"):
        assert labelled in text


def test_labels_are_off_by_default(config):
    text = _visible(_all_segments(config), BUSY)

    assert "model Opus" not in text
    assert "cost $" not in text


def test_label_replaces_the_built_in_ctx_of_the_percent_style(config):
    updated = _with(config, labels=True)
    updated["segments"]["context"]["style"] = "percent"

    text = _visible(updated, CLEAN)

    assert "ctx 25%" in text
    assert "ctx ctx" not in text


def test_plain_labels_keep_the_effort_apart_from_the_model(config):
    text = _visible(_with(config, labels=True, separator="plain"), CLEAN)

    assert "model Sonnet 5 effort high" in text


def test_thinking_shows_whether_extended_thinking_is_on(config):
    updated = _with(config, "thinking")
    thinking = updated["segments"]["thinking"]

    on_runs = parse(_output(updated, _sample({"thinking": {"enabled": True}})))
    off_runs = parse(_output(updated, _sample({"thinking": {"enabled": False}})))

    on = next(run for run in on_runs if "think on" in run.text)
    off = next(run for run in off_runs if "think off" in run.text)
    assert on.style.bg == thinking["colors"]["on"]
    assert off.style.bg == thinking["colors"]["off"]


def test_thinking_is_hidden_when_claude_code_does_not_report_it(config):
    assert "think" not in _visible(_with(config, "thinking"), FRESH)


def test_thinking_ignores_a_non_boolean_value(config):
    assert "think" not in _visible(_with(config, "thinking"), _sample({"thinking": {"enabled": "yes"}}))


@pytest.mark.parametrize("option", ["labels", "wrap"])
def test_validation_rejects_a_non_boolean_option(config, option):
    broken = {**copy.deepcopy(config), option: "yes"}

    with pytest.raises(ConfigError, match=option):
        validate_config(broken)


def test_cli_toggles_labels_and_wrap(tmp_path, monkeypatch):
    config_dir = tmp_path / "cfg"
    monkeypatch.setattr(config_module, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config_module, "CONFIG_PATH", config_dir / "config.json")

    assert main(["toggle", "labels", "on"]) == EXIT_OK
    assert main(["toggle", "wrap", "off"]) == EXIT_OK

    saved = config_module.load_config()
    assert saved["labels"] is True
    assert saved["wrap"] is False


@pytest.mark.parametrize("glyphs", GLYPH_MODES)
def test_wrapping_never_separates_the_effort_from_its_model(config, glyphs):
    updated = {**_all_segments(config), "glyphs": glyphs}

    for columns in range(85, 115):  # the busy sample reaches the model around 98
        rows = [SGR_RE.sub("", row) for row in _output(updated, BUSY, columns).split("\n")]
        model_row = next(row for row in rows if "Opus 5" in row)
        assert "max" in model_row, f"split at {columns} columns: {rows}"
