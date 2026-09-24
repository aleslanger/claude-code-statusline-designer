"""Parse ANSI SGR-colored text (the statusline script's output) into styled runs."""
from __future__ import annotations

import re
from typing import NamedTuple

from claude_style.palette import nearest_code

DEFAULT = -1  # curses "terminal default" color (needs curses.use_default_colors)
SGR_RE = re.compile(r"\x1b\[([0-9;]*)m")
OTHER_ESCAPE_RE = re.compile(r"\x1b(?:\[[0-9;?]*[A-Za-z]|[()][A-Z0-9])")
BASIC_FG = range(30, 38)
BASIC_BG = range(40, 48)
BRIGHT_FG = range(90, 98)
BRIGHT_BG = range(100, 108)
BRIGHT_OFFSET = 8
EXTENDED_FG = 38
EXTENDED_BG = 48
MODE_256 = 5
MODE_RGB = 2


class Style(NamedTuple):
    fg: int = DEFAULT
    bg: int = DEFAULT
    bold: bool = False
    dim: bool = False


class Run(NamedTuple):
    text: str
    style: Style


def _extended_color(params: list[int], i: int) -> tuple[int | None, int]:
    """Reads `5;N` or `2;R;G;B` after a 38/48. Returns (color, params consumed)."""
    if i < len(params) and params[i] == MODE_256 and i + 1 < len(params):
        return params[i + 1], 2
    if i < len(params) and params[i] == MODE_RGB and i + 3 < len(params):
        return nearest_code(tuple(params[i + 1 : i + 4])), 4
    return None, len(params) - i


def _apply_sgr(style: Style, params: list[int]) -> Style:
    fg, bg, bold, dim = style
    i = 0
    while i < len(params):
        code = params[i]
        i += 1
        if code == 0:
            fg, bg, bold, dim = DEFAULT, DEFAULT, False, False
        elif code == 1:
            bold = True
        elif code == 2:
            dim = True
        elif code == 22:
            bold = dim = False
        elif code in BASIC_FG:
            fg = code - BASIC_FG.start
        elif code in BRIGHT_FG:
            fg = code - BRIGHT_FG.start + BRIGHT_OFFSET
        elif code == 39:
            fg = DEFAULT
        elif code in BASIC_BG:
            bg = code - BASIC_BG.start
        elif code in BRIGHT_BG:
            bg = code - BRIGHT_BG.start + BRIGHT_OFFSET
        elif code == 49:
            bg = DEFAULT
        elif code in (EXTENDED_FG, EXTENDED_BG):
            color, used = _extended_color(params, i)
            i += used
            if color is not None and code == EXTENDED_FG:
                fg = color
            elif color is not None:
                bg = color
    return Style(fg, bg, bold, dim)


def parse(text: str) -> list[Run]:
    runs: list[Run] = []
    style = Style()
    pos = 0
    for match in SGR_RE.finditer(text):
        chunk = OTHER_ESCAPE_RE.sub("", text[pos : match.start()])
        if chunk:
            runs.append(Run(chunk, style))
        params = [int(p) for p in match.group(1).split(";") if p] or [0]
        style = _apply_sgr(style, params)
        pos = match.end()
    tail = OTHER_ESCAPE_RE.sub("", text[pos:])
    if tail:
        runs.append(Run(tail, style))
    return runs
