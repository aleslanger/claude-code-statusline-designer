from claude_style.ansi import DEFAULT, Run, Style, parse
from claude_style.config import load_config
from claude_style.palette import parse_color
from claude_style.preview import SAMPLES, run_samples


def test_plain_text_has_default_style():
    assert parse("hello") == [Run("hello", Style())]


def test_256_color_foreground_and_background():
    runs = parse("\x1b[48;5;24m\x1b[38;5;255m dir ")

    assert runs == [Run(" dir ", Style(fg=255, bg=24))]


def test_true_color_is_mapped_to_nearest_256_code():
    runs = parse("\x1b[38;2;95;135;175m█")

    assert runs[0].style.fg == parse_color("#5f87af")


def test_reset_and_default_background_codes():
    runs = parse("\x1b[48;5;24ma\x1b[49mb\x1b[0mc")

    assert [r.style.bg for r in runs] == [24, DEFAULT, DEFAULT]


def test_basic_and_bright_colors_and_attributes():
    runs = parse("\x1b[34mx\x1b[1;92my\x1b[2mz\x1b[22mw")

    assert runs[0].style.fg == 4
    assert runs[1].style == Style(fg=10, bold=True)
    assert runs[2].style.dim
    assert not runs[3].style.bold and not runs[3].style.dim


def test_non_sgr_escapes_are_stripped():
    assert parse("\x1b[2Kab\x1b(Bc") == [Run("abc", Style())]


def test_truncated_extended_color_does_not_crash():
    assert parse("\x1b[38;5mx") == [Run("x", Style())]


def test_real_statusline_output_parses_to_visible_text(config):
    result = run_samples(config, SAMPLES[:1], columns=120)[0]

    text = "".join(r.text for r in parse(result.output))
    assert result.error == ""
    assert "Sonnet 5" in text
    assert "\x1b" not in text


def test_narrow_columns_shorten_the_path_in_preview(config):
    wide = run_samples(config, SAMPLES[:1], columns=150)[0].output
    narrow = run_samples(config, SAMPLES[:1], columns=40)[0].output

    assert "~/projects/my-app" in wide
    assert "~/projects" not in narrow and "my-app" in narrow


def test_preview_shows_git_segment_in_clean_and_dirty_colors(config):
    clean, dirty = run_samples(config, SAMPLES[:2], columns=120)
    git = config["segments"]["git"]

    clean_run = next(r for r in parse(clean.output) if "main" in r.text)
    dirty_run = next(r for r in parse(dirty.output) if "feature/login" in r.text)

    assert clean_run.style.bg == git["bg_clean"]
    assert dirty_run.style.bg == git["bg_dirty"]


def test_loaded_user_config_renders_without_errors():
    assert all(r.error == "" for r in run_samples(load_config()))
