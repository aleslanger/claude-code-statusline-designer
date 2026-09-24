"""Regenerate the README screenshots in docs/ as SVG plus 2x PNG (needs Chromium).

Every image comes from real output: theme strips run the generated statusline
script, menu shots drive the real curses menu in a pseudo-terminal (pyte).
Nerd Font glyphs are drawn as shapes so the SVGs render without special fonts.

Usage: make docs
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import NamedTuple
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]

from tty_session import DOWN, ENTER, RIGHT, TuiSession

from claude_style.ansi import DEFAULT, parse
from claude_style.palette import to_hex
from claude_style.presets import DARK_PRESETS, PRESETS
from claude_style.preview import SAMPLES, run_samples
from claude_style.schemes import scheme_config

DOCS = ROOT / "docs"
FAKE_USER, FAKE_HOST = "dev", "workstation"  # keep real account names out of public images
STATUSLINE_COLUMNS = 120
LABEL_WIDTH = 18
MENU_ROWS, MENU_COLS = 30, 96
PALETTE_HOVER_STEPS = 13
BROWSERS = ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable")
PNG_SCALE = 2  # retina-sharp PNGs
BROWSER_TIMEOUT_S = 60

CELL_W, CELL_H, FONT_SIZE = 8.4, 18, 14
PAD, TITLEBAR = 16, 30
BASELINE = 0.74  # text baseline as a fraction of the cell height
SHADE_DOT, SHADE_DOT_STEP = 1.4, 2.8  # dot size and spacing for the light-shade glyph
FONT = "ui-monospace, SFMono-Regular, Menlo, Consolas, 'DejaVu Sans Mono', monospace"
WINDOW_DOTS = ("#ff5f57", "#febc2e", "#28c840")
GLYPH_POWERLINE, GLYPH_GIT = "", ""  # the script prints the git icon as bytes EF 90 9C
WORD_RUN_RE = re.compile(r"\S+(?: \S+)*")  # text chunks separated by 2+ spaces are placed separately
GLYPH_FULL, GLYPH_SHADE, GLYPH_UPPER, GLYPH_LOWER = "█", "░", "▀", "▄"
SHAPES = {GLYPH_POWERLINE, GLYPH_FULL, GLYPH_SHADE, GLYPH_UPPER, GLYPH_LOWER}
PYTE_NAMED = {
    name: code
    for code, name in enumerate(
        ["black", "red", "green", "brown", "blue", "magenta", "cyan", "white"]
        + ["brightblack", "brightred", "brightgreen", "brightbrown", "brightblue", "brightmagenta", "brightcyan", "brightwhite"]
    )
}


class Theme(NamedTuple):
    bg: str
    fg: str
    dim: str
    chrome: str


DARK = Theme(bg="#1c1c1c", fg="#d0d0d0", dim="#8a8a8a", chrome="#2d2d2d")
LIGHT = Theme(bg="#ffffff", fg="#303030", dim="#8a8a8a", chrome="#e9e9e9")


class Cell(NamedTuple):
    char: str
    fg: str
    bg: str
    bold: bool = False


# --- sources ---------------------------------------------------------------

def _ansi_cells(text: str, theme: Theme) -> list[Cell]:
    cells = []
    for run in parse(text):
        fg = to_hex(run.style.fg) if run.style.fg != DEFAULT else theme.fg
        bg = to_hex(run.style.bg) if run.style.bg != DEFAULT else theme.bg
        cells += [Cell(ch, fg, bg, run.style.bold) for ch in run.text]
    return cells


def _label(text: str, theme: Theme) -> list[Cell]:
    return [Cell(ch, theme.dim, theme.bg) for ch in text.ljust(LABEL_WIDTH)]


def theme_rows(names: list[str], theme: Theme) -> list[list[Cell]]:
    rows: list[list[Cell]] = []
    for name in names:
        results = run_samples(scheme_config(name), SAMPLES[:2], columns=STATUSLINE_COLUMNS)
        for i, result in enumerate(results):
            if result.error:
                raise RuntimeError(f"{name}: {result.error}")
            rows.append(_label(name if i == 0 else "", theme) + _ansi_cells(result.output, theme))
        rows.append([])
    return rows[:-1]


def _pyte_color(value: str, default: str) -> str:
    if value == "default":
        return default
    if value in PYTE_NAMED:
        return to_hex(PYTE_NAMED[value])
    return f"#{value}"


def screen_rows(session: TuiSession, theme: Theme) -> list[list[Cell]]:
    screen = session.screen
    rows = []
    for y in range(screen.lines):
        row = []
        for x in range(screen.columns):
            ch = screen.buffer[y][x]
            fg, bg = _pyte_color(ch.fg, theme.fg), _pyte_color(ch.bg, theme.bg)
            if ch.reverse:
                fg, bg = bg, fg
            row.append(Cell(ch.data or " ", fg, bg, ch.bold))
        rows.append(row)
    return rows


# --- SVG -------------------------------------------------------------------

def _shape(cell: Cell, x: float, y: float) -> str:
    if cell.char == GLYPH_POWERLINE:
        points = f"{x:.1f},{y} {x + CELL_W:.1f},{y + CELL_H / 2} {x:.1f},{y + CELL_H}"
        return f'<polygon points="{points}" fill="{cell.fg}"/>'
    if cell.char == GLYPH_SHADE:
        return f'<rect x="{x:.1f}" y="{y}" width="{CELL_W}" height="{CELL_H}" fill="url(#{_shade_id(cell.fg)})"/>'
    height, top = {
        GLYPH_FULL: (CELL_H, 0),
        GLYPH_UPPER: (CELL_H / 2, 0),
        GLYPH_LOWER: (CELL_H / 2, CELL_H / 2),
    }[cell.char]
    return f'<rect x="{x:.1f}" y="{y + top}" width="{CELL_W}" height="{height}" fill="{cell.fg}"/>'


def _shade_id(color: str) -> str:
    return f"shade{color.lstrip('#')}"


def _shade_patterns(rows: list[list[Cell]]) -> list[str]:
    """Dot patterns imitating the light-shade glyph, one per color used."""
    colors = sorted({c.fg for row in rows for c in row if c.char == GLYPH_SHADE})
    return [
        f'<pattern id="{_shade_id(c)}" width="{SHADE_DOT_STEP}" height="{SHADE_DOT_STEP}" patternUnits="userSpaceOnUse">'
        f'<rect width="{SHADE_DOT}" height="{SHADE_DOT}" fill="{c}"/></pattern>'
        for c in colors
    ]


def _backgrounds(row: list[Cell], y: float, theme: Theme) -> list[str]:
    out, start = [], 0
    for i in range(1, len(row) + 1):
        if i == len(row) or row[i].bg != row[start].bg:
            if row[start].bg != theme.bg:
                x, width = PAD + start * CELL_W, (i - start) * CELL_W
                out.append(f'<rect x="{x:.1f}" y="{y}" width="{width:.1f}" height="{CELL_H}" fill="{row[start].bg}"/>')
            start = i
    return out


def _text_runs(row: list[Cell], y: float) -> list[str]:
    out, start = [], 0
    for i in range(1, len(row) + 1):
        boundary = i == len(row) or row[i].char in SHAPES or row[start].char in SHAPES
        if not boundary and (row[i].fg, row[i].bold) == (row[start].fg, row[start].bold):
            continue
        cell = row[start]
        x = PAD + start * CELL_W
        if cell.char in SHAPES:
            out.append(_shape(cell, x, y))
        else:
            out += _text(row[start:i], x, y)
        start = i
    return out


def _git_icon(x: float, y: float, color: str) -> str:
    """Branch icon (two commits and a fork) standing in for the Nerd Font glyph."""
    stroke = f'stroke="{color}" stroke-width="1.4" fill="none" stroke-linecap="round"'
    return (
        f'<g {stroke}><path d="M{x + 2.6:.1f},{y + 4} V{y + 13}"/>'
        f'<path d="M{x + 6.6:.1f},{y + 6.4} C{x + 6.6:.1f},{y + 10} {x + 2.6:.1f},{y + 9} {x + 2.6:.1f},{y + 11.5}"/>'
        f'<circle cx="{x + 2.6:.1f}" cy="{y + 14.2}" r="1.6"/><circle cx="{x + 6.6:.1f}" cy="{y + 4.8}" r="1.6"/></g>'
    )


def _text(cells: list[Cell], x: float, y: float) -> list[str]:
    """Places each word run at its exact cell, so no renderer's whitespace handling can shift or stretch it."""
    out = []
    raw = "".join(c.char for c in cells)
    for offset, char in enumerate(raw):
        if char == GLYPH_GIT:
            out.append(_git_icon(x + offset * CELL_W, y, cells[offset].fg))
    raw = raw.replace(GLYPH_GIT, " ")
    weight = ' font-weight="bold"' if cells[0].bold else ""
    for match in WORD_RUN_RE.finditer(raw):
        chunk = match.group()
        out.append(
            f'<text x="{x + match.start() * CELL_W:.1f}" y="{y + CELL_H * BASELINE:.1f}" fill="{cells[0].fg}"{weight} '
            f'textLength="{len(chunk) * CELL_W:.1f}" lengthAdjust="spacingAndGlyphs">{escape(chunk)}</text>'
        )
    return out


def svg(rows: list[list[Cell]], theme: Theme, title: str) -> str:
    width = max(len(r) for r in rows) * CELL_W + 2 * PAD
    height = len(rows) * CELL_H + TITLEBAR + 2 * PAD
    parts = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
            f'viewBox="0 0 {width:.0f} {height:.0f}" font-family="{FONT}" font-size="{FONT_SIZE}">'
        ),
        "<defs>",
        *_shade_patterns(rows),
        "</defs>",
        f'<rect width="100%" height="100%" rx="10" fill="{theme.chrome}"/>',
        f'<rect y="{TITLEBAR}" width="100%" height="{height - TITLEBAR - 10}" fill="{theme.bg}"/>',
        f'<rect y="{height - 20}" width="100%" height="20" rx="10" fill="{theme.bg}"/>',
    ]
    parts += [f'<circle cx="{20 + i * 20}" cy="{TITLEBAR / 2}" r="6" fill="{c}"/>' for i, c in enumerate(WINDOW_DOTS)]
    parts.append(f'<text x="{width / 2:.0f}" y="{TITLEBAR / 2 + 5}" fill="{theme.dim}" text-anchor="middle">{escape(title)}</text>')
    for y_index, row in enumerate(rows):
        y = TITLEBAR + PAD + y_index * CELL_H
        parts += _backgrounds(row, y, theme) + _text_runs(row, y)
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


# --- main ------------------------------------------------------------------

def _fake_identity() -> None:
    bin_dir = Path(tempfile.mkdtemp(prefix="claude-style-shots-"))
    for name, value in (("whoami", FAKE_USER), ("hostname", FAKE_HOST)):
        tool = bin_dir / name
        tool.write_text(f"#!/bin/sh\necho {value}\n", encoding="utf-8")
        tool.chmod(0o755)
    os.environ["PATH"] = f"{bin_dir}{os.pathsep}{os.environ['PATH']}"


def _menu_shots() -> dict[str, list[list[Cell]]]:
    session = TuiSession(Path(tempfile.mkdtemp()), rows=MENU_ROWS, cols=MENU_COLS, env={"COLORTERM": "truecolor"})
    try:
        session.select_row("current directory")
        menu = screen_rows(session, DARK)
        session.send("c")
        session.send(ENTER)
        session.send(DOWN + RIGHT * PALETTE_HOVER_STEPS)
        palette = screen_rows(session, DARK)
    finally:
        session.kill()
    return {"menu": menu, "palette": palette}


def main() -> None:
    _fake_identity()
    os.environ["COLORTERM"] = "truecolor"
    DOCS.mkdir(exist_ok=True)
    dark_names = list(DARK_PRESETS)
    light_names = [n for n in PRESETS if n.endswith("-light")]
    shots = {
        "themes-dark.svg": svg(theme_rows(dark_names, DARK), DARK, "dark themes"),
        "themes-light.svg": svg(theme_rows(light_names, LIGHT), LIGHT, "light themes"),
    }
    menus = _menu_shots()
    shots["menu.svg"] = svg(menus["menu"], DARK, "claude-style")
    shots["palette.svg"] = svg(menus["palette"], DARK, "claude-style — color palette")
    browser = _find_browser()
    for name, content in shots.items():
        svg_path = DOCS / name
        svg_path.write_text(content, encoding="utf-8")
        png_path = _render_png(browser, svg_path)
        print(f"wrote docs/{name} + docs/{png_path.name}")


def _find_browser() -> str:
    for candidate in BROWSERS:
        path = shutil.which(candidate)
        if path:
            return path
    raise SystemExit(f"PNG export needs a Chromium-based browser on PATH (tried: {', '.join(BROWSERS)})")


def _render_png(browser: str, svg_path: Path) -> Path:
    """PNG twin of an SVG. PyPI can't show SVGs from GitHub (served as text/plain), PNGs work everywhere."""
    size = re.search(r'width="(\d+)" height="(\d+)"', svg_path.read_text(encoding="utf-8"))
    png_path = svg_path.with_suffix(".png")
    result = subprocess.run(
        [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--default-background-color=00000000",  # transparent, so the rounded corners stay round
            f"--force-device-scale-factor={PNG_SCALE}",
            f"--window-size={size.group(1)},{size.group(2)}",
            f"--screenshot={png_path}",
            svg_path.as_uri(),
        ],
        capture_output=True,
        text=True,
        timeout=BROWSER_TIMEOUT_S,
        check=False,
    )
    if result.returncode != 0 or not png_path.is_file():
        raise SystemExit(f"{browser} failed to render {svg_path.name}:\n{result.stderr.strip()}")
    return png_path


if __name__ == "__main__":
    main()
