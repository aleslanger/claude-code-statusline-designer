"""Reset: return colors (or the whole look) to the scheme a config was derived from."""
from __future__ import annotations

from claude_style.config import COLOR_FIELDS, CUSTOM_PRESET, get_color, set_color
from claude_style.schemes import SchemeError, scheme_config

IDENTITY_KEYS = frozenset({"preset", "based_on"})


def base_scheme_name(config: dict) -> str | None:
    if config["preset"] == CUSTOM_PRESET:
        return config.get("based_on")
    return config["preset"]


def base_config(config: dict) -> dict:
    name = base_scheme_name(config)
    if name is None:
        raise SchemeError("these colors aren't based on a known scheme, so there's nothing to reset to")
    try:
        return scheme_config(name)
    except SchemeError:
        raise SchemeError(f"the scheme '{name}' these colors came from no longer exists") from None


def _look(config: dict) -> dict:
    return {k: v for k, v in config.items() if k not in IDENTITY_KEYS}


def is_modified(config: dict, base: dict) -> bool:
    return _look(config) != _look(base)


def modified_fields(config: dict, base: dict, segment: str) -> set[str]:
    return {
        path
        for path, _label in COLOR_FIELDS[segment]
        if get_color(config, segment, path) != get_color(base, segment, path)
    }


def reset_fields(config: dict, segment: str, paths: list[str]) -> None:
    """Resets the given color fields in place, like set_color. Raises SchemeError if there's no base."""
    base = base_config(config)
    for path in paths:
        set_color(config, segment, path, get_color(base, segment, path))
    if config["preset"] == CUSTOM_PRESET and not is_modified(config, base):
        config["preset"], config["based_on"] = base["preset"], None
