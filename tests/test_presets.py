import os

import pytest

from claude_style.ansi import parse
from claude_style.contrast import (
    DARK_TERMINAL_BG,
    LIGHT_TERMINAL_BG,
    MIN_SUBTLE_CONTRAST,
    readability_issues,
)
from claude_style.palette import contrast_ratio, nearest_code
from claude_style.presets import DARK_PRESETS, PRESETS
from claude_style.preview import SAMPLES, run_samples
from claude_style.schemes import scheme_config

FILLED_BLOCK = "█"
BUSY_SAMPLE = SAMPLES[1]  # 90% context -> uses the highest threshold color
GRADIENT_SAMPLE_POINTS = (5, 50, 95)


def _terminal_bg(name: str) -> int:
    return LIGHT_TERMINAL_BG if name.endswith("-light") else DARK_TERMINAL_BG


@pytest.mark.parametrize("name", list(PRESETS))
def test_every_preset_is_readable(name):
    issues = readability_issues(scheme_config(name), _terminal_bg(name))

    assert issues == [], "\n".join(f"{i.segment}: {i.describe()}" for i in issues)


@pytest.mark.parametrize("name", list(DARK_PRESETS))
def test_every_dark_preset_has_a_light_variant_right_after_it(name):
    names = list(PRESETS)

    assert names[names.index(name) + 1] == f"{name}-light"


def _gradient_code(pct: int, peak: int) -> int:
    """Mirror of gradient_rgb in the generated script, mapped the way the menu maps it."""
    if pct <= 50:
        rgb = (pct * peak // 50, peak, 0)
    else:
        rgb = (peak, peak - (pct - 50) * peak // 50, 0)
    return nearest_code(rgb)


@pytest.mark.parametrize("name", list(PRESETS))
def test_gradient_blocks_stand_out_from_the_bar_background(name):
    ctx = scheme_config(name)["segments"]["context"]
    ratios = [contrast_ratio(_gradient_code(p, ctx["gradient_peak"]), ctx["bar_bg"]) for p in GRADIENT_SAMPLE_POINTS]

    assert min(ratios) >= MIN_SUBTLE_CONTRAST, ratios


def _filled_block_runs(name: str, monkeypatch) -> list:
    monkeypatch.setitem(os.environ, "COLORTERM", "")
    output = run_samples(scheme_config(name), [BUSY_SAMPLE], columns=120)[0].output
    return [run for run in parse(output) if FILLED_BLOCK in run.text]


@pytest.mark.parametrize("name", [n for n in PRESETS if PRESETS[n]["separator"] == "powerline"])
def test_filled_bar_blocks_are_visible_without_true_color(name, monkeypatch):
    # Regression: in 256-color mode the blocks were drawn in the segment's own
    # background color, so the bar looked empty however full the context was.
    runs = _filled_block_runs(name, monkeypatch)

    assert runs, "no filled blocks rendered"
    assert all(run.style.fg != run.style.bg for run in runs)


def test_plain_mode_shows_the_threshold_color_without_true_color(monkeypatch):
    # Regression: plain mode drew the percentage in the text color, so
    # 'minimal' never turned red at 90% context on 256-color terminals.
    monkeypatch.setitem(os.environ, "COLORTERM", "")
    config = scheme_config("minimal")
    red = config["segments"]["context"]["thresholds"][2][1]

    output = run_samples(config, [BUSY_SAMPLE], columns=120)[0].output
    percent = next(run for run in parse(output) if "%" in run.text)

    assert percent.style.fg == red
