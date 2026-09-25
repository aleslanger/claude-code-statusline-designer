"""End-to-end tests of the curses menu: real process, real pty, emulated screen.

pyte rebuilds the screen from curses' output, so assertions check what a user
would actually see -- characters and their colors -- not internal state.
"""
from __future__ import annotations

import pytest

from claude_style.palette import to_hex

pytest.importorskip("pyte")

from tty_session import (
    CTRL_C,
    DOWN,
    ENTER,
    FAKE_USER,
    LEFT,
    RIGHT,
    TuiSession,
)

DIR_BG_DEFAULT = 24
USER_HOST_BG_DEFAULT = 236
HOVER_SWEEP = 140  # enough hovered colors to exceed 255 pairs if they were never recycled
SWEEP_MAX_WAIT_S = 60.0  # each hover re-runs the preview script (~100 ms)


def _pyte_bg(code: int) -> str:
    return to_hex(code).lstrip("#")


@pytest.fixture
def tui(tmp_path):
    session = TuiSession(tmp_path)
    yield session
    session.kill()


def _open_dir_color_editor(tui: TuiSession) -> None:
    tui.select_row("current directory")
    tui.send("c")


def test_main_menu_shows_live_statusline_preview(tui):
    row = tui.preview_row()

    assert "Sonnet 5" in tui.screen.display[row]
    assert "Opus 5" in tui.screen.display[row + 1]
    assert tui.bg_of(row, "my-app") == _pyte_bg(DIR_BG_DEFAULT)


def test_nudging_a_color_repaints_the_preview_immediately(tui):
    _open_dir_color_editor(tui)
    tui.send(RIGHT)

    assert tui.bg_of(tui.preview_row(), "my-app") == _pyte_bg(DIR_BG_DEFAULT + 1)


def test_palette_previews_hovered_color_and_cancel_restores_it(tui):
    _open_dir_color_editor(tui)
    tui.send(ENTER)
    tui.send(RIGHT)
    tui.send(RIGHT)

    assert tui.bg_of(tui.preview_row(), "my-app") == _pyte_bg(DIR_BG_DEFAULT + 2)

    tui.send("q")
    assert tui.bg_of(tui.preview_row(), "my-app") == _pyte_bg(DIR_BG_DEFAULT)


def test_preview_colors_stay_correct_after_hovering_many_palette_colors(tui):
    # Regression: color pair ids above 255 wrap inside curses attributes, so
    # once a session had allocated that many pairs (the palette grid, plus new
    # preview pairs for every hovered color) later screens showed wrong colors.
    _open_dir_color_editor(tui)
    tui.send(ENTER)
    hovered = DIR_BG_DEFAULT + HOVER_SWEEP
    tui.send(RIGHT * HOVER_SWEEP, max_wait=0)
    tui.wait_for(f"code {hovered} ", max_wait=SWEEP_MAX_WAIT_S)  # the palette's info line

    assert tui.bg_of(tui.preview_row(), "my-app") == _pyte_bg(hovered)

    tui.send("q")  # cancel palette
    tui.send("q")  # back to main menu

    row = tui.preview_row()
    assert tui.bg_of(row, "my-app") == _pyte_bg(DIR_BG_DEFAULT)
    assert tui.bg_of(row, f"{FAKE_USER}@") == _pyte_bg(USER_HOST_BG_DEFAULT)


def test_toggling_a_segment_updates_preview_without_leaving_the_menu(tui):
    tui.select_row("current directory")
    tui.send(" ")

    assert "my-app" not in tui.screen.display[tui.preview_row()]
    assert "Preview (press Enter" not in tui.screen_text()


def test_glyphs_row_switches_the_preview_to_ascii(tui):
    tui.select_row("Glyphs")
    tui.send(RIGHT)  # nerdfont -> unicode
    tui.send(RIGHT)  # unicode -> ascii

    assert "ascii" in tui.selected_line()
    assert "#########." in tui.screen.display[tui.preview_row() + 1]


def test_context_mood_word_toggle_shows_in_the_preview(tui):
    tui.select_row("context mood word")
    tui.send(" ")

    row = tui.preview_row()
    assert "Coasting" in tui.screen.display[row]
    assert "Dumb" in tui.screen.display[row + 1]


def test_r_in_color_editor_resets_the_field_and_clears_unsaved(tui):
    _open_dir_color_editor(tui)
    tui.send(RIGHT)
    assert "was 24" in tui.screen_text()
    assert tui.bg_of(tui.preview_row(), "my-app") == _pyte_bg(DIR_BG_DEFAULT + 1)

    tui.send("r")

    assert "was 24" not in tui.screen_text()
    assert tui.bg_of(tui.preview_row(), "my-app") == _pyte_bg(DIR_BG_DEFAULT)
    tui.send("q")
    assert "unsaved" not in tui.screen_text()


def test_color_editor_warns_about_unreadable_text(tui):
    _open_dir_color_editor(tui)
    tui.send(DOWN)  # text color
    tui.send("#")
    tui.send("24" + ENTER)  # same as the background -> invisible text

    assert "hard to read: text on background 1.0:1" in tui.screen_text()


def test_capital_r_resets_every_color_of_the_segment(tui):
    _open_dir_color_editor(tui)
    tui.send(RIGHT)
    tui.send(DOWN)
    tui.send(LEFT)  # text color defaults to 255, the maximum, so nudge it down
    assert tui.screen_text().count("was ") == 2

    tui.send("R")

    assert "was " not in tui.screen_text()


def test_reset_row_undoes_all_changes_after_confirmation(tui):
    tui.select_row("current directory")
    tui.send(" ")
    assert "my-app" not in tui.screen.display[tui.preview_row()]

    tui.select_row("Reset to 'agnoster'")
    tui.send(ENTER)
    tui.send("y" + ENTER)

    assert "my-app" in tui.screen.display[tui.preview_row()]
    assert "(no changes)" in tui.screen_text()


def test_exit_without_changes_quits_immediately_and_writes_nothing(tui, tmp_path):
    tui.select_row("Exit without saving")
    tui.send(ENTER)

    assert tui.finish() == 0
    assert not (tmp_path / ".config/claude-style/config.json").exists()


def test_exit_with_changes_asks_and_can_be_declined(tui, tmp_path):
    tui.select_row("current directory")
    tui.send(" ")
    tui.select_row("Exit without saving")
    tui.send(ENTER)
    assert "discard unsaved changes?" in tui.screen_text()

    tui.send("n" + ENTER)
    assert "nothing was discarded" in tui.screen_text()

    tui.send(ENTER)
    tui.send("y" + ENTER)
    assert tui.finish() == 0
    assert not (tmp_path / ".config/claude-style/config.json").exists()


def test_save_scheme_from_the_menu(tui, tmp_path):
    tui.send("s")
    tui.send("mine" + ENTER)

    assert "Saved 'mine'" in "\n".join(tui.screen.display)
    assert (tmp_path / ".config/claude-style/schemes/mine.json").is_file()


def test_ctrl_c_exits_cleanly_with_130(tui):
    tui.send(CTRL_C)

    assert tui.finish() == 130
    assert "Traceback" not in "\n".join(tui.screen.display)
