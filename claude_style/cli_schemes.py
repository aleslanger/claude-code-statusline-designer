"""`claude-style scheme ...` subcommands: list, save, delete, export, import."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from claude_style.config import CUSTOM_PRESET, save_config
from claude_style.presets import PRESETS
from claude_style.schemes import (
    MAX_SCHEME_BYTES,
    SchemeError,
    all_scheme_names,
    delete_scheme,
    export_config,
    export_scheme,
    import_scheme,
    read_scheme_file,
    save_scheme,
    scheme_config,
    write_export,
)

STDIN_MARKER = "-"
DEFAULT_EXPORT_NAME = "my-scheme"


def add_scheme_parser(sub) -> None:
    p = sub.add_parser("scheme", help="save, list, delete, import and export your own color schemes")
    ss = p.add_subparsers(dest="scheme_command", required=True)

    ss.add_parser("list", help="list built-in presets and your saved schemes")

    p_save = ss.add_parser("save", help="save your current look as a named scheme")
    p_save.add_argument("name")
    p_save.add_argument("--overwrite", action="store_true", help="replace an existing scheme with this name")

    p_delete = ss.add_parser("delete", help="delete one of your saved schemes")
    p_delete.add_argument("name")

    p_export = ss.add_parser("export", help="write a scheme as a shareable JSON file")
    p_export.add_argument("name", nargs="?", help="scheme to export (default: your current look)")
    p_export.add_argument("-o", "--output", help="file to write (default: print to stdout)")
    p_export.add_argument("--overwrite", action="store_true", help="replace the output file if it exists")

    p_import = ss.add_parser("import", help="import a scheme file someone shared with you")
    p_import.add_argument("file", help=f"scheme file, or '{STDIN_MARKER}' to read stdin")
    p_import.add_argument("--name", help="save it under a different name")
    p_import.add_argument("--overwrite", action="store_true", help="replace your scheme if the name is taken")
    p_import.add_argument("--apply", action="store_true", help="also switch to it right away")


def _read_import_source(source: str) -> str:
    if source != STDIN_MARKER:
        return read_scheme_file(Path(source).expanduser())
    text = sys.stdin.read(MAX_SCHEME_BYTES + 1)
    if len(text) > MAX_SCHEME_BYTES:
        raise SchemeError(f"stdin is larger than the {MAX_SCHEME_BYTES}-byte scheme limit")
    return text


def _list() -> None:
    for name in all_scheme_names():
        print(f"{name:<14} {'built-in' if name in PRESETS else 'yours'}")


def _export(args: argparse.Namespace, config: dict) -> None:
    if args.name:
        text = export_scheme(args.name)
    else:
        name = config["preset"] if config["preset"] != CUSTOM_PRESET else DEFAULT_EXPORT_NAME
        text = export_config(config, name)
    if not args.output:
        sys.stdout.write(text)
        return
    path = write_export(text, Path(args.output).expanduser(), overwrite=args.overwrite)
    print(f"exported -> {path.resolve()}")


def _import(args: argparse.Namespace) -> None:
    name = import_scheme(_read_import_source(args.file), name=args.name, overwrite=args.overwrite)
    print(f"imported '{name}'")
    if args.apply:
        save_config(scheme_config(name))
        print(f"switched to '{name}'. Run 'claude-style install' to apply it to the statusline.")


def run_scheme_command(args: argparse.Namespace, config: dict) -> None:
    command = args.scheme_command
    if command == "list":
        _list()
    elif command == "save":
        path = save_scheme(args.name, config, overwrite=args.overwrite)
        config["preset"] = args.name
        save_config(config)
        print(f"saved '{args.name}' -> {path}")
    elif command == "delete":
        path = delete_scheme(args.name)
        if config["preset"] == args.name:
            config["preset"], config["based_on"] = CUSTOM_PRESET, None
            save_config(config)
        print(f"deleted '{args.name}' ({path})")
    elif command == "export":
        _export(args, config)
    elif command == "import":
        _import(args)
