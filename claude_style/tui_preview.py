"""Live statusline preview drawn inside the curses menu.

Runs the real generated script (not an approximation) against sample data
and paints its ANSI output with curses color pairs. Results are cached per
(config, width), so redraws that don't change anything don't spawn bash.
"""
from __future__ import annotations

import curses
import json

from claude_style import ansi
from claude_style.preview import SAMPLES, SampleResult, run_samples
from claude_style.tui_widgets import ERROR_BG, addstr, pair
from claude_style.validate import ConfigError

LIVE_SAMPLE_COUNT = 2  # clean session + busy session (dirty repo, max effort, 90% context)
TITLE = "LIVE PREVIEW"
SUBTITLE = "clean session · busy session"
LEFT_MARGIN = 2
BLOCK_ROWS = 1 + 1 + LIVE_SAMPLE_COUNT  # blank spacer + title + samples


class LivePreview:
    def __init__(self) -> None:
        self._key: tuple[str, int] | None = None
        self._results: list[SampleResult] = []

    def results(self, config: dict, columns: int) -> list[SampleResult]:
        key = (json.dumps(config, sort_keys=True), columns)
        if key != self._key:
            try:
                self._results = run_samples(config, SAMPLES[:LIVE_SAMPLE_COUNT], columns)
            except ConfigError as exc:
                self._results = [SampleResult("error", "", str(exc))]
            self._key = key
        return self._results


def _style_attr(style: ansi.Style) -> int:
    p = pair(style.fg, style.bg)
    attr = curses.color_pair(p) if p is not None else curses.A_NORMAL
    if style.bold:
        attr |= curses.A_BOLD
    if style.dim:
        attr |= curses.A_DIM
    return attr


def _draw_runs(stdscr, y: int, x: int, runs: list[ansi.Run]) -> None:
    width = stdscr.getmaxyx()[1]
    for run in runs:
        if x >= width - 1:
            return
        addstr(stdscr, y, x, run.text, _style_attr(run.style))
        x += len(run.text)


def draw(stdscr, live: LivePreview, config: dict, top: int, bottom: int) -> None:
    """Draws the title and as many sample lines as fit in rows [top, bottom)."""
    if bottom - top < 2:
        return
    width = stdscr.getmaxyx()[1]
    addstr(stdscr, top, LEFT_MARGIN, TITLE, curses.A_BOLD | curses.A_DIM)
    addstr(stdscr, top, LEFT_MARGIN + len(TITLE) + 2, SUBTITLE, curses.A_DIM)

    error_pair = pair(curses.COLOR_WHITE, ERROR_BG)
    error_attr = curses.color_pair(error_pair) if error_pair is not None else curses.A_REVERSE
    for offset, result in enumerate(live.results(config, width - LEFT_MARGIN)):
        y = top + 1 + offset
        if y >= bottom:
            return
        if result.error:
            addstr(stdscr, y, LEFT_MARGIN, f" script error: {result.error.splitlines()[0]} ", error_attr)
        else:
            _draw_runs(stdscr, y, LEFT_MARGIN, ansi.parse(result.output))
