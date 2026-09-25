"""Interactive + scriptable CLI for Claude Code Statusline Designer."""
import argparse
import copy
import json
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from claude_style.cli_schemes import add_scheme_parser, run_scheme_command
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
from claude_style.glyphs import GLYPH_MODE_LABELS, GLYPH_MODES
from claude_style.installer import STATUSLINE_PATH, InstallError, install, uninstall
from claude_style.palette import parse_color, to_hex
from claude_style.presets import PRESETS
from claude_style.preview import preview
from claude_style.reset import base_config, is_modified, reset_fields
from claude_style.schemes import (
    all_scheme_names,
    export_config,
    import_scheme,
    read_scheme_file,
    save_scheme,
    scheme_config,
    write_export,
)
from claude_style.validate import ConfigError

DISTRIBUTION = "claude-code-statusline-designer"
CONTEXT_WORD_TOGGLE = "context-word"  # `toggle context-word on` = the Smart -> Dumb mood word
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_INTERRUPTED = 130  # shell convention: 128 + SIGINT


def _print_menu(config: dict, installed: bool) -> None:
    print("\n=== Claude Code Statusline Designer ===")
    status = "already installed - changes below are not live until you install again" if installed else "not installed yet"
    print(f"({status})")
    print(f"scheme: {config['preset']}   separator: {config['separator']}\n")
    print("Segments:")
    for i, key in enumerate(SEGMENT_ORDER, start=1):
        state = "on " if config["segments"][key]["enabled"] else "off"
        print(f"  {i}. [{state}] {SEGMENT_LABELS[key]}")
    print("\n  p. choose a scheme (shows a preview of each)")
    print("  s. toggle separator style (powerline/plain)")
    print(f"  g. cycle glyphs (now: {config['glyphs']} - {GLYPH_MODE_LABELS[config['glyphs']]})")
    word = "on" if config["segments"]["context"]["state_word"] else "off"
    print(f"  o. context mood word Smart -> Dumb (now: {word})")
    print("  c. edit a segment's individual colors")
    print("  w. save current look as your own scheme")
    print("  x. export current look to a file")
    print("  m. import a scheme file")
    print("  r. reset everything back to the scheme you started from")
    print("  v. preview current config in this terminal")
    print("  i. install (write statusline + wire into settings.json)")
    print("  u. uninstall (remove statusLine from settings.json)")
    print("  q. save selections and quit without installing")
    print("  e. exit without saving")


def _pick_number(prompt_text: str, count: int):
    pick = input(prompt_text).strip()
    if pick.isdigit() and 1 <= int(pick) <= count:
        return int(pick) - 1
    return None


def _choose_scheme_with_preview(config: dict) -> dict:
    names = all_scheme_names()
    for i, name in enumerate(names, start=1):
        tag = "" if name in PRESETS else "  (yours)"
        print(f"\n  {i}. {name}{tag}")
        preview(scheme_config(name))
    idx = _pick_number("\nscheme number (blank to cancel): ", len(names))
    return scheme_config(names[idx]) if idx is not None else config


def _edit_colors_classic(config: dict) -> dict:
    segments = [s for s in SEGMENT_ORDER if s in COLOR_FIELDS]
    for i, key in enumerate(segments, start=1):
        print(f"  {i}. {SEGMENT_LABELS[key]}")
    seg_idx = _pick_number("\nsegment number (blank to cancel): ", len(segments))
    if seg_idx is None:
        return config
    segment = segments[seg_idx]

    fields = COLOR_FIELDS[segment]
    for i, (path, label) in enumerate(fields, start=1):
        value = get_color(config, segment, path)
        print(f"  {i}. {label:<18} {value:>3}  {to_hex(value)}")
    field_idx = _pick_number("\nfield number (blank to cancel): ", len(fields))
    if field_idx is None:
        return config
    path, label = fields[field_idx]

    raw = input(f"new color for '{label}' (0-255 or #rrggbb): ")
    try:
        set_color(config, segment, path, parse_color(raw))
    except ValueError as exc:
        print(f"skipped: {exc}")
        return config
    preview(config)
    return config


def _save_scheme_classic(config: dict) -> dict:
    name = input("save scheme as (blank to cancel): ").strip()
    if not name:
        return config
    overwrite = input(f"overwrite '{name}' if it exists? [y/N] ").strip().lower() == "y"
    path = save_scheme(name, config, overwrite=overwrite)
    config["preset"] = name
    print(f"saved '{name}' -> {path}")
    return config


def _export_classic(config: dict) -> None:
    name = config["preset"] if config["preset"] != CUSTOM_PRESET else "my-scheme"
    target = input(f"export to file [{name}.claude-style.json]: ").strip() or f"{name}.claude-style.json"
    path = write_export(export_config(config, name), Path(target).expanduser())
    print(f"exported -> {path.resolve()}")


def _import_classic(config: dict) -> dict:
    source = input("scheme file to import (blank to cancel): ").strip()
    if not source:
        return config
    rename = input("save under a different name? (blank = keep the file's name): ").strip() or None
    name = import_scheme(read_scheme_file(Path(source).expanduser()), name=rename)
    print(f"imported '{name}'")
    imported = scheme_config(name)
    preview(imported)
    return imported


def _reset_classic(config: dict) -> dict:
    base = base_config(config)
    if not is_modified(config, base):
        print(f"nothing to reset - already matches '{base['preset']}'")
        return config
    if input(f"discard all changes and return to '{base['preset']}'? [y/N] ").strip().lower() != "y":
        return config
    preview(base)
    return base


def interactive_main(classic: bool = False) -> None:
    if not classic and sys.stdin.isatty() and sys.stdout.isatty():
        try:
            from claude_style import tui

            tui.run()
            return
        except (KeyboardInterrupt, ConfigError):
            raise
        except Exception as exc:  # noqa: BLE001 -- curses failure modes vary by terminal; any of them should fall back
            print(f"(arrow-key menu unavailable: {exc}; falling back to the classic menu)\n")

    classic_menu()


def _classic_action(choice: str, config: dict) -> dict:
    """Handles the menu choices that edit config in place and keep the menu open."""
    if choice == "v":
        preview(config)
    elif choice == "s":
        config["separator"] = "plain" if config["separator"] == "powerline" else "powerline"
        preview(config)
    elif choice == "p":
        config = _choose_scheme_with_preview(config)
    elif choice == "c":
        config = _edit_colors_classic(config)
    elif choice == "w":
        config = _save_scheme_classic(config)
    elif choice == "x":
        _export_classic(config)
    elif choice == "m":
        config = _import_classic(config)
    elif choice == "r":
        config = _reset_classic(config)
    elif choice == "g":
        modes = list(GLYPH_MODES)
        config["glyphs"] = modes[(modes.index(config["glyphs"]) + 1) % len(modes)]
        preview(config)
    elif choice == "o":
        ctx = config["segments"]["context"]
        ctx["state_word"] = not ctx["state_word"]
        preview(config)
    elif choice.isdigit() and 1 <= int(choice) <= len(SEGMENT_ORDER):
        key = SEGMENT_ORDER[int(choice) - 1]
        config["segments"][key]["enabled"] = not config["segments"][key]["enabled"]
        preview(config)
    else:
        print("unrecognized choice")
    return config


def classic_menu() -> None:
    config = load_config()
    original = copy.deepcopy(config)
    print("Current config, rendered with your last saved settings:")
    preview(config)

    while True:
        _print_menu(config, installed=STATUSLINE_PATH.exists())
        choice = input("\n> ").strip().lower()

        if choice == "e":
            if config != original and input("discard unsaved changes? [y/N] ").strip().lower() != "y":
                continue
            print("Exited without saving - your config is unchanged.")
            return
        if choice == "q":
            save_config(config)
            print("Selections saved. Run 'claude-style' again to keep editing, or 'claude-style install' when ready.")
            return
        if choice == "i":
            path = install(config)
            save_config(config)
            print(f"\nInstalled -> {path}")
            print("Open a new Claude Code session to see it. Run 'claude-style' again any time to change it.")
            return
        if choice == "u":
            removed = uninstall()
            print("statusLine removed from settings.json" if removed else "no statusLine entry was set")
            return
        try:
            config = _classic_action(choice, config)
        except ConfigError as exc:
            print(f"error: {exc}")


def _version() -> str:
    try:
        return version(DISTRIBUTION)
    except PackageNotFoundError:
        return "unknown (not installed)"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="claude-style", description="Design, preview and install a Claude Code statusline.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {_version()}")
    sub = parser.add_subparsers(dest="command")

    p_menu = sub.add_parser("menu", help="interactive menu (default)")
    p_menu.add_argument("--classic", action="store_true", help="use the numbered menu instead of arrow-key navigation")

    p_preset = sub.add_parser("preset", help="switch to a built-in preset or one of your schemes")
    p_preset.add_argument("name", help="see 'claude-style presets'")

    p_toggle = sub.add_parser("toggle", help="enable/disable a segment")
    p_toggle.add_argument("segment", choices=[*SEGMENT_ORDER, CONTEXT_WORD_TOGGLE])
    p_toggle.add_argument("state", choices=["on", "off"])

    p_glyphs = sub.add_parser("glyphs", help="glyph set: nerdfont, unicode (no Nerd Font needed) or ascii")
    p_glyphs.add_argument("mode", choices=list(GLYPH_MODES))

    p_sep = sub.add_parser("separator", help="set separator style")
    p_sep.add_argument("style", choices=["powerline", "plain"])

    p_color = sub.add_parser("color", help="list or set individual segment colors")
    color_sub = p_color.add_subparsers(dest="color_command")
    color_sub.add_parser("list", help="show every editable color field and its current value")
    p_color_set = color_sub.add_parser("set", help="set one color field")
    p_color_set.add_argument("segment", choices=list(COLOR_FIELDS))
    p_color_set.add_argument("field", help="e.g. bg, fg, colors.low, thresholds.0.1 (see 'color list')")
    p_color_set.add_argument("value", help="256-color code (0-255) or hex '#rrggbb' (mapped to the nearest code)")
    p_color_reset = color_sub.add_parser("reset", help="return colors to the scheme you started from")
    p_color_reset.add_argument("segment", choices=list(COLOR_FIELDS))
    p_color_reset.add_argument("field", nargs="?", help="one field (default: every color of the segment)")

    sub.add_parser("reset", help="undo all changes: return to the scheme you started from")
    add_scheme_parser(sub)

    sub.add_parser("preview", help="render sample output in this terminal")
    sub.add_parser("install", help="write statusline script and register it")
    sub.add_parser("uninstall", help="remove statusLine from settings.json, restore previous script")
    sub.add_parser("show", help="print current config as JSON")
    sub.add_parser("presets", help="list built-in presets and your saved schemes")

    return parser


def main(argv=None) -> int:
    try:
        _dispatch(argv)
    except KeyboardInterrupt:
        # curses.wrapper has already restored the terminal by the time this propagates.
        print("\nCancelled - nothing was saved.")
        return EXIT_INTERRUPTED
    except (ConfigError, InstallError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    return EXIT_OK


def _require_field(segment: str, field: str) -> None:
    if field not in dict(COLOR_FIELDS[segment]):
        fields = ", ".join(f for f, _ in COLOR_FIELDS[segment])
        raise ConfigError(f"unknown field '{field}' for {segment}. available: {fields}")


def _color_reset(args: argparse.Namespace, config: dict) -> None:
    if args.field:
        _require_field(args.segment, args.field)
    paths = [args.field] if args.field else [p for p, _ in COLOR_FIELDS[args.segment]]
    reset_fields(config, args.segment, paths)
    save_config(config)
    for path in paths:
        value = get_color(config, args.segment, path)
        print(f"{args.segment}.{path} -> {value} ({to_hex(value)})")


def _color_command(args: argparse.Namespace, config: dict) -> None:
    if args.color_command == "reset":
        _color_reset(args, config)
        return
    if args.color_command != "set":
        for segment, fields in COLOR_FIELDS.items():
            print(f"\n{segment} ({SEGMENT_LABELS[segment]}):")
            for path, label in fields:
                value = get_color(config, segment, path)
                print(f"  {path:<16} {label:<18} {value:>3}  {to_hex(value)}")
        return
    _require_field(args.segment, args.field)
    try:
        value = parse_color(args.value)
    except ValueError as exc:
        raise ConfigError(str(exc)) from None
    set_color(config, args.segment, args.field, value)
    save_config(config)
    print(f"{args.segment}.{args.field} -> {value} ({to_hex(value)})")


def _dispatch(argv) -> None:
    args = build_parser().parse_args(argv)

    if args.command is None:
        interactive_main()
        return
    if args.command == "menu":
        interactive_main(classic=args.classic)
        return

    config = load_config()

    if args.command == "preset":
        save_config(scheme_config(args.name))
        print(f"scheme set to {args.name}. Run 'claude-style install' to apply it.")
    elif args.command == "toggle":
        if args.segment == CONTEXT_WORD_TOGGLE:
            config["segments"]["context"]["state_word"] = args.state == "on"
        else:
            config["segments"][args.segment]["enabled"] = args.state == "on"
        save_config(config)
        print(f"{args.segment} -> {args.state}")
    elif args.command == "glyphs":
        config["glyphs"] = args.mode
        save_config(config)
        print(f"glyphs -> {args.mode} ({GLYPH_MODE_LABELS[args.mode]})")
    elif args.command == "separator":
        config["separator"] = args.style
        save_config(config)
        print(f"separator -> {args.style}")
    elif args.command == "color":
        _color_command(args, config)
    elif args.command == "reset":
        base = base_config(config)
        save_config(base)
        print(f"reset to '{base['preset']}'. Run 'claude-style install' to apply it.")
    elif args.command == "scheme":
        run_scheme_command(args, config)
    elif args.command == "preview":
        preview(config)
    elif args.command == "install":
        print(f"installed -> {install(config)}")
    elif args.command == "uninstall":
        removed = uninstall()
        print("statusLine removed from settings.json" if removed else "no statusLine entry was set")
    elif args.command == "show":
        print(json.dumps(config, indent=2, ensure_ascii=False))
    elif args.command == "presets":
        for name in all_scheme_names():
            print(name if name in PRESETS else f"{name}  (yours)")


if __name__ == "__main__":
    sys.exit(main())
