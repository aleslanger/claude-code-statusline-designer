"""Reusable curses building blocks for the Claude Code Statusline Designer menu."""
from __future__ import annotations

import curses

from claude_style.palette import contrast_fg, parse_color, to_hex

TITLE = "Claude Code Statusline Designer"
TAGLINE = "design \u00b7 preview \u00b7 install"
ACCENT_BG = 62
OK_BG = 28
WARN_BG = 130
ERROR_BG = 124
PALETTE_SIZE = 256
PALETTE_COLS = 16
# Each grid character is "▀": foreground paints the top half, background the
# bottom half, so one color pair shows two palette entries stacked vertically.
PALETTE_CHAR_ROWS = PALETTE_SIZE // (PALETTE_COLS * 2)
CODES_PER_CHAR_ROW = PALETTE_COLS * 2
HALF_TOP = "▀"
HALF_BOTTOM = "▄"
CELL_WIDTH = 3
CELL_STRIDE = CELL_WIDTH + 1  # one-column gap holds the selection markers
GRID_LEFT = 4
MARKER_FG = 231
KEY_ESC = 27
ENTER_KEYS = (curses.KEY_ENTER, 10, 13)
PROMPT_MAX_LEN = 200

_color_pairs: dict[tuple[int, int], int] = {}
_next_pair_id = 1


def _max_pair_id() -> int:
    # The pair number lives in the A_COLOR bits of an attribute (8 bits), so
    # color_pair(n) for n > 255 silently wraps to a different pair.
    return min(curses.COLOR_PAIRS - 1, curses.A_COLOR >> 8)


def begin_frame() -> None:
    """Forget all pair allocations; every screen redraws fully, so ids can be reused per frame."""
    global _next_pair_id
    _color_pairs.clear()
    _next_pair_id = 1


def pair(fg: int, bg: int):
    """Allocate (and cache) a color pair for this frame.

    Returns None on <256-color terminals or when the frame ran out of pairs --
    callers then draw without color rather than with a wrong one.
    """
    global _next_pair_id
    if not curses.has_colors() or curses.COLORS < PALETTE_SIZE:
        return None
    key = (fg, bg)
    if key not in _color_pairs:
        if _next_pair_id > _max_pair_id():
            return None
        try:
            curses.init_pair(_next_pair_id, fg, bg)
        except curses.error:
            return None
        _color_pairs[key] = _next_pair_id
        _next_pair_id += 1
    return _color_pairs[key]


def swatch_attr(code: int):
    """Attr for text drawn on top of `code` as background, with a readable foreground."""
    p = pair(contrast_fg(code), code)
    return curses.color_pair(p) if p is not None else None


def addstr(stdscr, y: int, x: int, text: str, attr=curses.A_NORMAL) -> None:
    """addstr that clips at the window edge instead of raising."""
    height, width = stdscr.getmaxyx()
    if y < 0 or y >= height or x < 0 or x >= width:
        return
    try:
        stdscr.addstr(y, x, text[: max(0, width - x - 1)], attr)
    except curses.error:
        pass


def header(stdscr, subtitle: str) -> int:
    """Title bar shared by every screen (and the start of every frame). Returns the first free row."""
    begin_frame()
    stdscr.erase()
    width = stdscr.getmaxyx()[1]
    accent = pair(curses.COLOR_WHITE, ACCENT_BG)
    bar = curses.color_pair(accent) if accent is not None else curses.A_REVERSE
    addstr(stdscr, 0, 0, " " * (width - 1), bar)
    addstr(stdscr, 0, 2, f" {TITLE} ", bar | curses.A_BOLD)
    addstr(stdscr, 0, len(TITLE) + 4, TAGLINE, bar)
    addstr(stdscr, 1, 2, subtitle, curses.A_DIM)
    return 3


def footer(stdscr, text: str) -> None:
    height, width = stdscr.getmaxyx()
    addstr(stdscr, height - 1, 0, " " * (width - 1), curses.A_REVERSE)
    addstr(stdscr, height - 1, 2, text, curses.A_REVERSE)


def status_line(stdscr, message: str, is_error: bool) -> None:
    if not message:
        return
    height = stdscr.getmaxyx()[0]
    p = pair(curses.COLOR_WHITE, ERROR_BG if is_error else OK_BG)
    attr = (curses.color_pair(p) if p is not None else curses.A_REVERSE) | curses.A_BOLD
    addstr(stdscr, height - 2, 2, f" {message} ", attr)


def prompt(stdscr, label: str, default: str = "") -> str | None:
    """One-line text input on the status row. Empty input (with no default) cancels."""
    height, width = stdscr.getmaxyx()
    y = height - 2
    suffix = f" [{default}]" if default else " (empty = cancel)"
    text = f"{label}{suffix}: "
    addstr(stdscr, y, 0, " " * (width - 1))
    addstr(stdscr, y, 2, text, curses.A_BOLD)
    stdscr.refresh()
    curses.echo()
    curses.curs_set(1)
    try:
        raw = stdscr.getstr(y, min(2 + len(text), width - 2), PROMPT_MAX_LEN)
    finally:
        curses.noecho()
        curses.curs_set(0)
    value = raw.decode("utf-8", errors="replace").strip()
    return value or (default or None)


def confirm(stdscr, question: str) -> bool:
    answer = prompt(stdscr, f"{question} [y/N]", default="n")
    return answer is not None and answer.lower() in ("y", "yes", "a", "ano")


def _draw_grid(stdscr, top: int, selected: int) -> bool:
    """Draws the half-block grid. Returns False if the terminal can't show it."""
    for char_row in range(PALETTE_CHAR_ROWS):
        for col in range(PALETTE_COLS):
            upper = char_row * CODES_PER_CHAR_ROW + col
            p = pair(upper, upper + PALETTE_COLS)
            if p is None:
                return False
            addstr(stdscr, top + char_row, GRID_LEFT + col * CELL_STRIDE, HALF_TOP * CELL_WIDTH, curses.color_pair(p))

    char_row, rest = divmod(selected, CODES_PER_CHAR_ROW)
    is_upper, col = rest < PALETTE_COLS, rest % PALETTE_COLS
    marker_pair = pair(MARKER_FG, -1)
    marker_attr = curses.color_pair(marker_pair) | curses.A_BOLD if marker_pair is not None else curses.A_BOLD
    marker = HALF_TOP if is_upper else HALF_BOTTOM
    x = GRID_LEFT + col * CELL_STRIDE
    addstr(stdscr, top + char_row, x - 1, marker, marker_attr)
    addstr(stdscr, top + char_row, x + CELL_WIDTH, marker, marker_attr)
    return True


def _draw_palette(stdscr, selected: int, title: str, on_draw=None) -> None:
    top = header(stdscr, f"Palette → {title}")
    if not _draw_grid(stdscr, top, selected):
        addstr(stdscr, top, GRID_LEFT, "This terminal can't show a 256-color grid - press # to type a code.", curses.A_DIM)

    info_y = top + PALETTE_CHAR_ROWS + 1
    big = swatch_attr(selected)
    addstr(stdscr, info_y, 4, f"  {selected:>3}  ", big if big is not None else curses.A_REVERSE)
    addstr(stdscr, info_y, 13, f"code {selected}  ·  {to_hex(selected)}", curses.A_BOLD)
    footer(stdscr, "arrows move   enter pick   # type hex/code   q cancel")
    if on_draw is not None:
        on_draw(stdscr, selected, info_y + 1)
    stdscr.refresh()


def pick_from_palette(stdscr, current: int, title: str, on_draw=None) -> int | None:
    """Full 256-color grid picker. Returns the chosen code, or None if cancelled.

    `on_draw(stdscr, hovered_code, first_free_row)` lets the caller paint extra
    content (e.g. a live preview of the hovered color) under the grid.
    """
    selected = current
    while True:
        _draw_palette(stdscr, selected, title, on_draw)
        ch = stdscr.getch()
        if ch == curses.KEY_LEFT:
            selected = (selected - 1) % PALETTE_SIZE
        elif ch == curses.KEY_RIGHT:
            selected = (selected + 1) % PALETTE_SIZE
        elif ch == curses.KEY_UP:
            selected = (selected - PALETTE_COLS) % PALETTE_SIZE
        elif ch == curses.KEY_DOWN:
            selected = (selected + PALETTE_COLS) % PALETTE_SIZE
        elif ch in ENTER_KEYS:
            return selected
        elif ch == ord("#"):
            typed = prompt(stdscr, "hex (#5e81ac) or code (0-255)")
            if typed is None:
                continue
            try:
                selected = parse_color(typed)
            except ValueError:
                curses.beep()
        elif ch in (ord("q"), KEY_ESC):
            return None
