"""User color schemes: save, list, delete, import and export.

A scheme is a full config snapshot (colors, enabled segments, separator), the
same shape as a built-in preset. On disk and in exported files it is wrapped
in a small envelope so a random JSON file is never mistaken for a scheme:

    {"format": "claude-style-scheme", "version": 1, "name": "...", "config": {...}}
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from claude_style.config import CONFIG_DIR, CUSTOM_PRESET, DEFAULT_CONFIG, _deep_merge
from claude_style.presets import PRESETS
from claude_style.validate import NAME_RE, ConfigError, validate_config, validate_name

SCHEMES_DIR = CONFIG_DIR / "schemes"
SCHEME_FORMAT = "claude-style-scheme"
SCHEME_VERSION = 1
MAX_SCHEME_BYTES = 64 * 1024
RESERVED_NAMES = frozenset({CUSTOM_PRESET})


class SchemeError(ConfigError):
    pass


def _scheme_path(name: str) -> Path:
    validate_name(name)
    return SCHEMES_DIR / f"{name}.json"


def _prune(data, template):
    """Drop keys the template doesn't know, so an imported file can't smuggle extra fields in."""
    if not isinstance(data, dict) or not isinstance(template, dict):
        return data
    return {k: _prune(v, template[k]) for k, v in data.items() if k in template}


def _as_named(config: dict, name: str) -> dict:
    """Copy of config labelled as scheme `name`. A named scheme is its own base, so based_on is cleared."""
    named = copy.deepcopy(config)
    named["preset"] = name
    named["based_on"] = None
    return named


def _build_config(raw, name: str) -> dict:
    if not isinstance(raw, dict):
        raise SchemeError("scheme 'config' must be a JSON object")
    config = copy.deepcopy(DEFAULT_CONFIG)
    _deep_merge(config, _prune(raw, DEFAULT_CONFIG))
    config = _as_named(config, name)
    validate_config(config)
    return config


def _parse_envelope(text: str) -> tuple[str, dict]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SchemeError(f"not valid JSON: {exc}") from None
    if not isinstance(data, dict) or data.get("format") != SCHEME_FORMAT:
        raise SchemeError(f"not a Claude Code Statusline Designer scheme file (expected \"format\": \"{SCHEME_FORMAT}\")")
    if data.get("version") != SCHEME_VERSION:
        raise SchemeError(f"unsupported scheme version {data.get('version')!r} (this build reads version {SCHEME_VERSION})")
    name = data.get("name")
    validate_name(name)
    return name, data.get("config")


def _envelope(name: str, config: dict) -> str:
    doc = {"format": SCHEME_FORMAT, "version": SCHEME_VERSION, "name": name, "config": _as_named(config, name)}
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


def user_scheme_names() -> list[str]:
    if not SCHEMES_DIR.is_dir():
        return []
    return sorted(p.stem for p in SCHEMES_DIR.glob("*.json") if NAME_RE.match(p.stem))


def all_scheme_names() -> list[str]:
    return list(PRESETS) + [n for n in user_scheme_names() if n not in PRESETS]


def is_user_scheme(name: str) -> bool:
    return name not in PRESETS and name in user_scheme_names()


def scheme_config(name: str) -> dict:
    """Full, validated config for a built-in preset or a saved user scheme."""
    if name in PRESETS:
        config = copy.deepcopy(DEFAULT_CONFIG)
        _deep_merge(config, PRESETS[name])
        return _as_named(config, name)
    path = _scheme_path(name)
    if not path.is_file():
        raise SchemeError(f"unknown scheme '{name}'. available: {', '.join(all_scheme_names())}")
    _stored_name, raw = _parse_envelope(read_scheme_file(path))
    return _build_config(raw, name)


def _check_writable_name(name: str, overwrite: bool) -> Path:
    path = _scheme_path(name)
    if name in PRESETS:
        raise SchemeError(f"'{name}' is a built-in preset, pick another name")
    if name in RESERVED_NAMES:
        raise SchemeError(f"'{name}' is reserved, pick another name")
    if path.exists() and not overwrite:
        raise SchemeError(f"scheme '{name}' already exists (use --overwrite to replace it)")
    return path


def save_scheme(name: str, config: dict, overwrite: bool = False) -> Path:
    path = _check_writable_name(name, overwrite)
    snapshot = _as_named(config, name)
    validate_config(snapshot)
    SCHEMES_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(_envelope(name, snapshot), encoding="utf-8")
    return path


def delete_scheme(name: str) -> Path:
    if name in PRESETS:
        raise SchemeError(f"'{name}' is a built-in preset and can't be deleted")
    path = _scheme_path(name)
    if not path.is_file():
        raise SchemeError(f"no saved scheme named '{name}'")
    path.unlink()
    return path


def export_scheme(name: str) -> str:
    return _envelope(name, scheme_config(name))


def export_config(config: dict, name: str) -> str:
    validate_name(name)
    snapshot = _as_named(config, name)
    validate_config(snapshot)
    return _envelope(name, snapshot)


def read_scheme_file(path: Path) -> str:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise SchemeError(f"can't read {path}: {exc.strerror}") from None
    if size > MAX_SCHEME_BYTES:
        raise SchemeError(f"{path} is {size} bytes; scheme files are capped at {MAX_SCHEME_BYTES}")
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise SchemeError(f"can't read {path}: {exc}") from None


def write_export(text: str, path: Path, overwrite: bool = False) -> Path:
    if path.exists() and not overwrite:
        raise SchemeError(f"{path} already exists (use --overwrite to replace it)")
    try:
        path.write_text(text, encoding="utf-8")
    except OSError as exc:
        raise SchemeError(f"can't write {path}: {exc.strerror}") from None
    return path


def scheme_name_in(text: str) -> str:
    return _parse_envelope(text)[0]


def is_name_taken(name: str) -> bool:
    return name in PRESETS or name in RESERVED_NAMES or _scheme_path(name).exists()


def import_scheme(text: str, name: str | None = None, overwrite: bool = False) -> str:
    """Validate and save a scheme from exported text. Returns the name it was saved under."""
    stored_name, raw = _parse_envelope(text)
    target = name or stored_name
    config = _build_config(raw, target)
    save_scheme(target, config, overwrite=overwrite)
    return target
