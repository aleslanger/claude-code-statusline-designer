"""Arrow-key interactive menu for Claude Code Statusline Designer, built on stdlib curses.

Falls back to the numbered menu (claude_style.cli.classic_menu) when curses
isn't usable -- no tty, dumb terminal, or piped stdin/stdout.
"""
from __future__ import annotations

import copy
import curses
from dataclasses import dataclass, field
from pathlib import Path

from claude_style.config import (
    COLOR_FIELDS,
    CUSTOM_PRESET,
    SEGMENT_LABELS,
    SEGMENT_ORDER,
    get_color,
    load_config,
    save_config,
    set_color,
)
from claude_style.contrast import readability_issues
from claude_style.installer import STATUSLINE_PATH, install, uninstall
from claude_style.palette import parse_color, to_hex
from claude_style.preview import preview
from claude_style.reset import base_config, is_modified, modified_fields, reset_fields
from claude_style.schemes import (
    all_scheme_names,
    delete_scheme,
    export_config,
    import_scheme,
    is_name_taken,
    is_user_scheme,
    read_scheme_file,
    save_scheme,
    scheme_config,
    scheme_name_in,
    user_scheme_names,
    write_export,
)
from claude_style.tui_preview import BLOCK_ROWS as PREVIEW_BLOCK_ROWS
from claude_style.tui_preview import LivePreview
from claude_style.tui_preview import draw as draw_live_preview
from claude_style.tui_widgets import (
    ENTER_KEYS,
    KEY_ESC,
    OK_BG,
    WARN_BG,
    addstr,
    confirm,
    footer,
    header,
    pair,
    pick_from_palette,
    prompt,
    status_line,
    swatch_attr,
)
from claude_style.validate import ConfigError

HELP = "↑↓ move  ←→ change  space toggle  c colors  s save scheme  v full preview  q quit"
COLOR_HELP = "↑↓ field  ←→ ±1  PgUp/PgDn ±16  enter palette  # hex  r reset  R reset all  q back"
MODIFIED_MARK = "•"
MAX_CONTRAST_WARNINGS = 3
ESC_DELAY_MS = 25
COLOR_STEP_FINE = 1
COLOR_STEP_COARSE = 16
LIST_TOP = 4
RESERVED_BOTTOM_ROWS = 2  # status line + footer
TRAILING_SWATCH = 4
TRAILING_HINT = 5
MIN_LIST_ROWS = 6  # below this, the live preview is hidden to leave room for the menu

_ROWS = (
    [("section", "Theme"), ("preset", None), ("separator", None), ("reset", None)]
    + [("section", "Segments")]
    + [("segment", key) for key in SEGMENT_ORDER]
    + [("section", "Your schemes")]
    + [("save_scheme", None), ("export", None), ("import", None), ("delete_scheme", None)]
    + [("section", "Actions")]
    + [("preview", None), ("install", None), ("uninstall", None), ("quit", None), ("exit", None)]
)

_STATIC_ROW_TEXT = {
    "save_scheme": "★  Save current look as a scheme…",
    "export": "⇧  Export current look to a file…",
    "import": "⇩  Import a scheme file…",
    "delete_scheme": "✕  Delete a saved scheme…",
    "preview": "▶  Full-screen preview (all samples, true color)",
    "install": "⤓  Install — write statusline + register it",
    "uninstall": "✗  Uninstall — remove statusLine from settings.json",
    "quit": "⮐  Save selections & quit (no install)",
    "exit": "⏻  Exit without saving",
}


@dataclass
class MenuState:
    cursor: int
    top: int = 0
    message: str = ""
    is_error: bool = False
    pending_discard: bool = False
    original: dict = field(default_factory=dict)  # config as loaded, to detect unsaved changes on Exit
    live: LivePreview = field(default_factory=LivePreview)

    def say(self, message: str, is_error: bool = False) -> None:
        self.message, self.is_error = message, is_error


def _short(path: Path) -> str:
    return str(path).replace(str(Path.home()), "~", 1)


def _scheme_tag(config: dict) -> str:
    name = config["preset"]
    if name == CUSTOM_PRESET:
        base = config.get("based_on")
        return f"  ● unsaved (from {base})" if base else "  ● unsaved"
    return "  ★ yours" if is_user_scheme(name) else ""


def _safe_base(config: dict) -> dict | None:
    try:
        return base_config(config)
    except ConfigError:
        return None


def _reset_row_text(config: dict) -> str:
    base = _safe_base(config)
    if base is None:
        return "↺  Reset (no base scheme to return to)"
    state = "undo all changes" if is_modified(config, base) else "no changes"
    return f"↺  Reset to '{base['preset']}' ({state})"


def _row_text(kind: str, key: str | None, config: dict) -> str:
    if kind == "preset":
        return f"Scheme      ‹ {config['preset']} ›{_scheme_tag(config)}"
    if kind == "separator":
        return f"Separator   ‹ {config['separator']} ›"
    if kind == "reset":
        return _reset_row_text(config)
    if kind == "segment":
        mark = "✓" if config["segments"][key]["enabled"] else " "
        return f"[{mark}] {SEGMENT_LABELS[key]}"
    return _STATIC_ROW_TEXT[kind]


def _selectable_indices() -> list[int]:
    return [i for i, (kind, _key) in enumerate(_ROWS) if kind != "section"]


def _list_space(stdscr) -> int:
    return stdscr.getmaxyx()[0] - LIST_TOP - RESERVED_BOTTOM_ROWS


def _preview_fits(stdscr) -> bool:
    return _list_space(stdscr) - PREVIEW_BLOCK_ROWS >= MIN_LIST_ROWS


def _visible_rows(stdscr) -> int:
    reserved_for_preview = PREVIEW_BLOCK_ROWS if _preview_fits(stdscr) else 0
    return max(1, _list_space(stdscr) - reserved_for_preview)


def _draw_bottom_preview(stdscr, live: LivePreview, config: dict) -> None:
    """Live preview pinned just above the status line and footer."""
    if not _preview_fits(stdscr):
        return
    bottom = stdscr.getmaxyx()[0] - RESERVED_BOTTOM_ROWS
    draw_live_preview(stdscr, live, config, bottom - PREVIEW_BLOCK_ROWS + 1, bottom)


def _scroll(state: MenuState, visible: int) -> None:
    if state.cursor < state.top:
        header_above = state.cursor > 0 and _ROWS[state.cursor - 1][0] == "section"
        state.top = state.cursor - 1 if header_above else state.cursor
    elif state.cursor >= state.top + visible:
        state.top = state.cursor - visible + 1


def _draw_row(stdscr, y: int, idx: int, state: MenuState, config: dict) -> None:
    kind, key = _ROWS[idx]
    if kind == "section":
        addstr(stdscr, y, 2, key.upper(), curses.A_BOLD | curses.A_DIM)
        return

    width = stdscr.getmaxyx()[1]
    selected = idx == state.cursor
    bg = config["segments"][key].get("bg", config["segments"][key].get("bg_clean")) if kind == "segment" else None
    has_hint = kind == "segment" and key in COLOR_FIELDS
    trailing = (TRAILING_SWATCH if bg is not None else 0) + (TRAILING_HINT if has_hint else 0)
    max_text = max(1, width - 3 - trailing - 1)
    text = f"{'▸ ' if selected else '  '}{_row_text(kind, key, config)}"
    if len(text) > max_text:
        text = text[: max_text - 1].rstrip() + "…"
    addstr(stdscr, y, 3, text.ljust(max_text), curses.A_REVERSE | curses.A_BOLD if selected else curses.A_NORMAL)

    attr = swatch_attr(bg) if bg is not None else None
    if attr is not None:
        addstr(stdscr, y, width - trailing - 1, "  ", attr)
    if has_hint:
        addstr(stdscr, y, width - TRAILING_HINT, "[c]", curses.A_DIM)


def _draw(stdscr, state: MenuState, config: dict) -> None:
    header(stdscr, f"scheme: {config['preset']}  ·  separator: {config['separator']}")
    width = stdscr.getmaxyx()[1]
    installed = STATUSLINE_PATH.exists()
    badge = " INSTALLED " if installed else " NOT INSTALLED "
    badge_pair = pair(0, OK_BG if installed else WARN_BG)
    if badge_pair is not None:
        addstr(stdscr, 1, width - len(badge) - 2, badge, curses.color_pair(badge_pair) | curses.A_BOLD)

    visible = _visible_rows(stdscr)
    _scroll(state, visible)
    for offset, idx in enumerate(range(state.top, min(len(_ROWS), state.top + visible))):
        _draw_row(stdscr, LIST_TOP + offset, idx, state, config)
    if state.top > 0:
        addstr(stdscr, LIST_TOP, width - 3, "▲", curses.A_DIM)
    if state.top + visible < len(_ROWS):
        addstr(stdscr, LIST_TOP + visible - 1, width - 3, "▼", curses.A_DIM)

    _draw_bottom_preview(stdscr, state.live, config)
    status_line(stdscr, state.message, state.is_error)
    footer(stdscr, HELP)
    stdscr.refresh()


def _draw_color_fields(stdscr, config: dict, segment: str, cursor: int, live: LivePreview) -> None:
    base = _safe_base(config)
    changed = modified_fields(config, base, segment) if base is not None else set()
    origin = f"  ·  {MODIFIED_MARK} = changed from '{base['preset']}'" if base is not None else ""
    y = header(stdscr, f"Colors → {SEGMENT_LABELS[segment]}{origin}") + 1
    for idx, (path, label) in enumerate(COLOR_FIELDS[segment]):
        value = get_color(config, segment, path)
        selected = idx == cursor
        attr = curses.A_REVERSE | curses.A_BOLD if selected else curses.A_NORMAL
        addstr(stdscr, y, 2, MODIFIED_MARK if path in changed else " ", curses.A_BOLD)
        addstr(stdscr, y, 4, f"{'▸ ' if selected else '  '}{label:<18}", attr)
        swatch = swatch_attr(value)
        addstr(stdscr, y, 26, f" {value:>3} ", swatch if swatch is not None else curses.A_DIM)
        addstr(stdscr, y, 33, to_hex(value), curses.A_DIM)
        if path in changed:
            addstr(stdscr, y, 42, f"was {get_color(base, segment, path)}", curses.A_DIM)
        y += 1
    _draw_contrast_warnings(stdscr, y + 1, config, segment)
    _draw_bottom_preview(stdscr, live, config)
    footer(stdscr, COLOR_HELP)
    stdscr.refresh()


def _draw_contrast_warnings(stdscr, y: int, config: dict, segment: str) -> None:
    issues = [i for i in readability_issues(config) if i.segment == segment]
    warn_pair = pair(0, WARN_BG)
    attr = curses.color_pair(warn_pair) if warn_pair is not None else curses.A_REVERSE
    for offset, issue in enumerate(issues[:MAX_CONTRAST_WARNINGS]):
        addstr(stdscr, y + offset, 4, f" ⚠ hard to read: {issue.describe()} ", attr)


def _palette_preview(live: LivePreview, config: dict, segment: str, path: str):
    """on_draw callback for the palette: previews the hovered color before it's picked."""

    def on_draw(stdscr, hovered: int, first_free_row: int) -> None:
        candidate = copy.deepcopy(config)
        set_color(candidate, segment, path, hovered)
        bottom = stdscr.getmaxyx()[0] - 1  # keep the footer
        draw_live_preview(stdscr, live, candidate, first_free_row, bottom)

    return on_draw


def _next_color(stdscr, ch: int, current: int, label: str, on_palette_draw=None) -> int | None:
    """New value for a color field given a key press, or None if the key isn't a color edit."""
    steps = {
        curses.KEY_LEFT: -COLOR_STEP_FINE,
        curses.KEY_RIGHT: COLOR_STEP_FINE,
        curses.KEY_PPAGE: -COLOR_STEP_COARSE,
        curses.KEY_NPAGE: COLOR_STEP_COARSE,
    }
    if ch in steps:
        return min(255, max(0, current + steps[ch]))
    if ch in ENTER_KEYS:
        return pick_from_palette(stdscr, current, label, on_palette_draw)
    if ch == ord("#"):
        typed = prompt(stdscr, "hex (#5e81ac) or code (0-255)")
        try:
            return parse_color(typed) if typed is not None else None
        except ValueError:
            curses.beep()
    return None


def _edit_colors(stdscr, config: dict, segment: str, live: LivePreview) -> None:
    fields = COLOR_FIELDS[segment]
    cursor = 0
    while True:
        _draw_color_fields(stdscr, config, segment, cursor, live)
        ch = stdscr.getch()
        if ch in (curses.KEY_UP, ord("k")):
            cursor = (cursor - 1) % len(fields)
        elif ch in (curses.KEY_DOWN, ord("j")):
            cursor = (cursor + 1) % len(fields)
        elif ch in (ord("q"), KEY_ESC):
            return
        elif ch in (ord("r"), ord("R")):
            paths = [p for p, _ in fields] if ch == ord("R") else [fields[cursor][0]]
            try:
                reset_fields(config, segment, paths)
            except ConfigError:
                curses.beep()
        else:
            path, label = fields[cursor]
            on_draw = _palette_preview(live, config, segment, path)
            value = _next_color(stdscr, ch, get_color(config, segment, path), label, on_draw)
            if value is not None:
                set_color(config, segment, path, value)


def _show_preview(config: dict) -> None:
    curses.endwin()
    print("\n\033[1mPreview\033[0m (press Enter to return to the menu)\n")
    preview(config)
    input()


def _save_as_scheme(stdscr, config: dict, state: MenuState) -> dict:
    default = config["preset"] if is_user_scheme(config["preset"]) else ""
    name = prompt(stdscr, "Save scheme as", default)
    if name is None:
        return config
    overwrite = is_user_scheme(name)
    if overwrite and not confirm(stdscr, f"Overwrite your scheme '{name}'?"):
        state.say("Not saved")
        return config
    try:
        path = save_scheme(name, config, overwrite=overwrite)
    except ConfigError as exc:
        state.say(str(exc), is_error=True)
        return config
    config["preset"] = name
    state.say(f"Saved '{name}' → {_short(path)}")
    return config


def _export(stdscr, config: dict, state: MenuState) -> dict:
    name = config["preset"]
    if name == CUSTOM_PRESET:
        name = prompt(stdscr, "Name inside the exported file", "my-scheme")
        if name is None:
            return config
    target = prompt(stdscr, "Export to file", f"{name}.claude-style.json")
    if target is None:
        return config
    path = Path(target).expanduser()
    overwrite = path.exists()
    if overwrite and not confirm(stdscr, f"{_short(path)} exists. Overwrite?"):
        state.say("Not exported")
        return config
    try:
        write_export(export_config(config, name), path, overwrite=overwrite)
    except ConfigError as exc:
        state.say(str(exc), is_error=True)
        return config
    state.say(f"Exported '{name}' → {_short(path.resolve())}")
    return config


def _import(stdscr, config: dict, state: MenuState) -> dict:
    source = prompt(stdscr, "Import scheme from file")
    if source is None:
        return config
    try:
        text = read_scheme_file(Path(source).expanduser())
        name = scheme_name_in(text)
        if is_name_taken(name):
            name = prompt(stdscr, f"'{name}' is taken — save it as")
            if name is None:
                state.say("Import cancelled")
                return config
        saved = import_scheme(text, name=name)
        imported = scheme_config(saved)
    except ConfigError as exc:
        state.say(f"Import failed: {exc}", is_error=True)
        return config
    state.say(f"Imported and applied '{saved}'")
    return imported


def _delete(stdscr, config: dict, state: MenuState) -> dict:
    names = user_scheme_names()
    if not names:
        state.say("You have no saved schemes yet")
        return config
    default = config["preset"] if config["preset"] in names else ""
    name = prompt(stdscr, f"Delete which scheme ({', '.join(names)})", default)
    if name is None:
        return config
    if not confirm(stdscr, f"Delete '{name}' permanently?"):
        state.say("Not deleted")
        return config
    try:
        delete_scheme(name)
    except ConfigError as exc:
        state.say(str(exc), is_error=True)
        return config
    if config["preset"] == name:
        config["preset"], config["based_on"] = CUSTOM_PRESET, None
    state.say(f"Deleted '{name}'")
    return config


def _reset_all(stdscr, config: dict, state: MenuState) -> dict:
    try:
        base = base_config(config)
    except ConfigError as exc:
        state.say(str(exc), is_error=True)
        return config
    if not is_modified(config, base):
        state.say(f"Nothing to reset — already matches '{base['preset']}'")
        return config
    if not confirm(stdscr, f"Discard all changes and return to '{base['preset']}'?"):
        state.say("Not reset")
        return config
    state.say(f"Reset to '{base['preset']}'")
    return base


_SCHEME_ACTIONS = {
    "save_scheme": _save_as_scheme,
    "export": _export,
    "import": _import,
    "delete_scheme": _delete,
    "reset": _reset_all,
}


def _cycle_scheme(config: dict, step: int, state: MenuState) -> dict | None:
    """Next/previous scheme, or None if the user first has to confirm discarding custom colors."""
    if config["preset"] == CUSTOM_PRESET and not state.pending_discard:
        state.pending_discard = True
        state.say("Unsaved custom colors — press ←/→ again to discard, or 's' to save them", is_error=True)
        return None
    names = all_scheme_names()
    if config["preset"] in names:
        target = names[(names.index(config["preset"]) + step) % len(names)]
    else:
        target = names[0] if step > 0 else names[-1]
    try:
        return scheme_config(target)
    except ConfigError as exc:
        state.say(f"Can't load '{target}': {exc}", is_error=True)
        return None


def _handle_activate(stdscr, kind: str, key: str | None, config: dict, state: MenuState) -> tuple[str | None, dict]:
    if kind == "segment":
        config["segments"][key]["enabled"] = not config["segments"][key]["enabled"]
    elif kind in _SCHEME_ACTIONS:
        config = _SCHEME_ACTIONS[kind](stdscr, config, state)
    elif kind == "preview":
        _show_preview(config)
    elif kind in ("install", "uninstall", "quit"):
        return kind, config
    elif kind == "exit":
        if config == state.original or confirm(stdscr, "Exit and discard unsaved changes?"):
            return "exit", config
        state.say("Still here — nothing was discarded")
    return None, config


def _handle_change(kind: str, ch: int, config: dict, state: MenuState) -> dict:
    step = 1 if ch == curses.KEY_RIGHT else -1
    if kind == "preset":
        switched = _cycle_scheme(config, step, state)
        if switched is None:
            return config
        state.say("")
        return switched
    if kind == "separator":
        config["separator"] = "plain" if config["separator"] == "powerline" else "powerline"
    return config


def _run(stdscr, config: dict) -> tuple[str, dict]:
    curses.curs_set(0)
    curses.set_escdelay(ESC_DELAY_MS)
    if curses.has_colors():
        # Lets the preview use the terminal's own background (color -1) where the script resets to it.
        curses.use_default_colors()
    stdscr.keypad(True)
    selectable = _selectable_indices()
    state = MenuState(cursor=selectable[0], original=copy.deepcopy(config))

    while True:
        _draw(stdscr, state, config)
        ch = stdscr.getch()
        kind, key = _ROWS[state.cursor]
        pos = selectable.index(state.cursor)
        was_pending, state.pending_discard = state.pending_discard, False
        if was_pending and ch not in (curses.KEY_LEFT, curses.KEY_RIGHT):
            state.say("")

        if ch in (curses.KEY_UP, ord("k")):
            state.cursor = selectable[(pos - 1) % len(selectable)]
        elif ch in (curses.KEY_DOWN, ord("j")):
            state.cursor = selectable[(pos + 1) % len(selectable)]
        elif ch in (curses.KEY_LEFT, curses.KEY_RIGHT):
            state.pending_discard = was_pending
            config = _handle_change(kind, ch, config, state)
        elif ch in (ord(" "), *ENTER_KEYS):
            action, config = _handle_activate(stdscr, kind, key, config, state)
            if action is not None:
                return action, config
        elif ch == ord("c") and kind == "segment" and key in COLOR_FIELDS:
            _edit_colors(stdscr, config, key, state.live)
        elif ch == ord("s"):
            config = _save_as_scheme(stdscr, config, state)
        elif ch == ord("v"):
            _show_preview(config)
        elif ch in (ord("q"), KEY_ESC):
            return "quit", config


def run() -> None:
    config = load_config()
    action, config = curses.wrapper(_run, config)

    if action == "install":
        save_config(config)
        path = install(config)
        print(f"\nInstalled -> {path}")
        print("Open a new Claude Code session to see it. Run 'claude-style' any time to change it.")
    elif action == "uninstall":
        removed = uninstall()
        print("statusLine removed from settings.json" if removed else "no statusLine entry was set")
    elif action == "exit":
        print("Exited without saving - your config is unchanged.")
    else:
        save_config(config)
        print("Selections saved. Run 'claude-style' again to keep editing, or 'claude-style install' when ready.")
