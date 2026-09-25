import copy
import re
import subprocess

import pytest

from claude_style.ansi import parse
from claude_style.glyphs import GLYPH_MODES
from claude_style.presets import PRESETS
from claude_style.preview import SAMPLES, run_samples
from claude_style.render import render
from claude_style.schemes import scheme_config
from claude_style.validate import ConfigError, validate_config

UNICODE_ESCAPE_RE = re.compile(r"\\[uU][0-9a-fA-F]{4}")
PRIVATE_USE = range(0xE000, 0xF900)  # Nerd Font icons live here
POWERLINE_ARROW = ""
CLEAN, BUSY = SAMPLES[0], SAMPLES[1]  # 25% and 90% context


def _visible(config: dict, sample: dict) -> str:
    result = run_samples(config, [sample], columns=120)[0]
    assert result.error == ""
    return "".join(run.text for run in parse(result.output))


def _with(config: dict, **changes) -> dict:
    updated = copy.deepcopy(config)
    for key, value in changes.items():
        if key == "state_word":
            updated["segments"]["context"]["state_word"] = value
        else:
            updated[key] = value
    return updated


@pytest.mark.parametrize("glyphs", GLYPH_MODES)
@pytest.mark.parametrize("name", list(PRESETS))
def test_generated_script_runs_on_bash_3_2(name, glyphs):
    # Regression: $'' printed the literal text "" on macOS, whose
    # /bin/bash 3.2 has no \u escapes. Only \xHH byte escapes are portable.
    script = render(_with(scheme_config(name), glyphs=glyphs, state_word=True))

    assert not UNICODE_ESCAPE_RE.search(script)
    assert subprocess.run(["bash", "-n"], input=script, text=True, capture_output=True, check=False).returncode == 0


def test_nerdfont_mode_draws_the_powerline_arrow(config):
    assert POWERLINE_ARROW in _visible(config, BUSY)


def test_unicode_mode_needs_no_nerd_font(config):
    text = _visible(_with(config, glyphs="unicode"), BUSY)

    assert not any(ord(ch) in PRIVATE_USE for ch in text)
    assert "⎇" in text  # the branch symbol stand-in


def test_ascii_mode_draws_only_ascii(config):
    text = _visible(_with(config, glyphs="ascii"), BUSY)

    assert text.isascii()
    assert "#########." in text  # 90% bar
    assert "feature/login *" in text  # dirty marker


@pytest.mark.parametrize(("sample", "word"), [(CLEAN, "Coasting"), (BUSY, "Dumb")])
def test_state_word_names_how_full_the_context_is(config, sample, word):
    assert f"{word} " in _visible(_with(config, state_word=True), sample)


def test_state_word_is_off_by_default(config):
    text = _visible(config, BUSY)

    assert "Dumb" not in text


def test_state_word_replaces_the_ctx_label_in_percent_style(config):
    config["segments"]["context"]["style"] = "percent"

    assert "Dumb 90%" in _visible(_with(config, state_word=True), BUSY)
    assert "ctx 90%" in _visible(config, BUSY)


def test_custom_state_labels_and_thresholds(config):
    ctx = config["segments"]["context"]
    ctx.update(state_word=True, state_labels=["a", "b", "c", "Mid", "Full"], state_thresholds=[5, 10, 20, 30])

    assert "Mid " in _visible(config, CLEAN)  # 25% falls in the 20-30 band
    assert "Full " in _visible(config, BUSY)  # 90% is past the last threshold


@pytest.mark.parametrize("label", ['Dumb"; rm -rf ~ #', "$(reboot)", "`id`", "x\\y", "", "x" * 17])
def test_state_labels_that_could_break_out_of_the_script_are_rejected(config, label):
    config["segments"]["context"]["state_labels"][4] = label

    with pytest.raises(ConfigError, match="state_labels"):
        validate_config(config)


@pytest.mark.parametrize("thresholds", [[50, 25, 70, 90], [25, 25, 70, 90], [25, 50, 70], [0, 50, 70, 90]])
def test_state_thresholds_must_be_four_ascending_percentages(config, thresholds):
    config["segments"]["context"]["state_thresholds"] = thresholds

    with pytest.raises(ConfigError, match="state_thresholds"):
        validate_config(config)


def test_unknown_glyph_mode_is_rejected(config):
    config["glyphs"] = "emoji"

    with pytest.raises(ConfigError, match="glyphs"):
        validate_config(config)
