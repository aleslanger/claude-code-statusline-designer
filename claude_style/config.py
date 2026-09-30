"""Config load/save for Claude Code Statusline Designer."""
import copy
import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "claude-style"
CONFIG_PATH = CONFIG_DIR / "config.json"
CUSTOM_PRESET = "custom"  # marks a config whose colors were edited but not saved as a scheme

SEGMENT_ORDER = [
    "user_host",
    "dir",
    "git",
    "pr",
    "session",
    "model",
    "effort",
    "thinking",
    "mode",
    "output_style",
    "context",
    "limits",
    "cost",
    "cache",
    "lines",
    "duration",
]

SEGMENT_LABELS = {
    "user_host": "user@host",
    "dir": "current directory",
    "git": "git branch/status",
    "pr": "pull request and review state",
    "session": "session name",
    "model": "model name",
    "effort": "effort level",
    "thinking": "extended thinking on/off",
    "mode": "fast mode, vim mode and agent",
    "output_style": "output style (only when non-default)",
    "context": "context usage bar",
    "limits": "plan usage limits (5h, weekly)",
    "cost": "session cost ($)",
    "cache": "prompt cache (hit ratio, warm/cold)",
    "lines": "lines added/removed",
    "duration": "session duration",
}

COLOR_FIELDS = {
    "user_host": [("bg", "background"), ("fg", "text")],
    "dir": [("bg", "background"), ("fg", "text")],
    "git": [("bg_clean", "clean background"), ("bg_dirty", "dirty background"), ("fg", "text")],
    "pr": [("bg", "background"), ("fg", "text")],
    "session": [("bg", "background"), ("fg", "text")],
    "mode": [("bg", "background"), ("fg", "text")],
    "model": [("bg", "background"), ("fg", "text")],
    "effort": [
        ("fg", "text"),
        ("colors.low", "low"),
        ("colors.medium", "medium"),
        ("colors.high", "high"),
        ("colors.xhigh", "xhigh"),
        ("colors.max", "max"),
        ("colors.default", "default"),
    ],
    "context": [
        ("fg", "text"),
        ("thresholds.0.1", "low threshold"),
        ("thresholds.1.1", "medium threshold"),
        ("thresholds.2.1", "high threshold"),
        ("bar_bg", "bar background"),
        ("bar_empty", "empty bar blocks"),
    ],
    "output_style": [("bg", "background"), ("fg", "text")],
    "limits": [("fg", "text"), ("colors.ok", "ok"), ("colors.warn", "warn"), ("colors.crit", "critical")],
    "cost": [("fg", "text"), ("colors.normal", "normal"), ("colors.warn", "warn")],
    "cache": [("fg", "text"), ("colors.warm", "warm"), ("colors.cold", "cold")],
    "thinking": [("fg", "text"), ("colors.on", "on"), ("colors.off", "off")],
    "lines": [("bg", "background"), ("fg", "text")],
    "duration": [("bg", "background"), ("fg", "text")],
}


# Short names printed before each value when labels are on. Segments whose
# text already says what it is (cache, thinking) have none.
SEGMENT_TAGS = {
    "user_host": "user",
    "dir": "dir",
    "git": "git",
    "pr": "PR",
    "session": "session",
    "model": "model",
    "effort": "effort",
    "mode": "mode",
    "output_style": "style",
    "context": "ctx",
    "limits": "limit",
    "cost": "cost",
    "lines": "lines",
    "duration": "time",
}


def segment_tag(config: dict, segment: str) -> str:
    """The label and a trailing space for a segment, or "" when labels are off."""
    tag = SEGMENT_TAGS.get(segment)
    return f"{tag} " if config["labels"] and tag else ""


def _walk_color_path(config: dict, segment: str, path: str) -> tuple[object, str]:
    node = config["segments"][segment]
    parts = path.split(".")
    for part in parts[:-1]:
        node = node[int(part)] if isinstance(node, list) else node[part]
    return node, parts[-1]


def get_color(config: dict, segment: str, path: str) -> int:
    node, last = _walk_color_path(config, segment, path)
    return node[int(last)] if isinstance(node, list) else node[last]


def set_color(config: dict, segment: str, path: str, value: int) -> None:
    if not 0 <= value <= 255:
        raise ValueError(f"color must be 0-255, got {value}")
    if get_color(config, segment, path) == value:
        return
    node, last = _walk_color_path(config, segment, path)
    if isinstance(node, list):
        node[int(last)] = value
    else:
        node[last] = value
    if config["preset"] != CUSTOM_PRESET:
        config["based_on"] = config["preset"]
    config["preset"] = CUSTOM_PRESET


DEFAULT_CONFIG = {
    "preset": "agnoster",
    "based_on": None,  # scheme a "custom" config was derived from; what Reset returns to
    "separator": "powerline",  # "powerline" or "plain"
    "glyphs": "nerdfont",  # "nerdfont", "unicode" (no Nerd Font needed) or "ascii"
    "labels": False,  # print a short name before each value, e.g. "ctx", "cost"
    "wrap": True,  # move segments to further rows when they don't fit into $COLUMNS
    "segments": {
        "user_host": {"enabled": True, "bg": 236, "fg": 250},
        "dir": {
            "enabled": True,
            "bg": 24,
            "fg": 255,
            "responsive": True,  # shorten the path when the terminal is narrow ($COLUMNS)
            "narrow_cols": 60,  # below this width: basename only
            "medium_cols": 100,  # below this width: last `medium_segments` path parts
            "medium_segments": 2,
        },
        "git": {
            "enabled": True,
            "bg_clean": 28,
            "bg_dirty": 130,
            "fg": 255,
        },
        "model": {"enabled": True, "bg": 33, "fg": 255},
        "effort": {
            "enabled": True,
            "fg": 255,
            "colors": {
                "low": 22,
                "medium": 94,
                "high": 130,
                "xhigh": 124,
                "max": 53,
                "default": 239,
            },
        },
        "context": {
            "enabled": True,
            "fg": 255,
            "style": "bar",  # "bar" or "percent"
            "thresholds": [[60, 28], [85, 166], [101, 160]],
            "true_color": True,  # smooth 24-bit gradient when $COLORTERM supports it
            "bar_bg": 238,  # segment background behind the true-color gradient bar
            "bar_empty": 235,  # unfilled bar blocks: a shade darker than bar_bg reads as "recessed"
            "gradient_peak": 255,  # brightest gradient channel; ~180 keeps it readable on light terminals
            # A word naming how full the context is, shown before the bar.
            # Idea and default labels/thresholds from Dumbometer (MIT) by Maximo Correa Rosas.
            "state_word": False,
            "state_labels": ["Smart", "Coasting", "Foggy", "Cooked", "Dumb"],
            "state_thresholds": [25, 50, 70, 90],  # usage % where labels 2-5 start
        },
        "output_style": {
            "enabled": False,
            "bg": 96,
            "fg": 255,
        },
        # The colors of the segments below are borrowed from each theme
        # (see preset_builders.usage_extras), so a theme never has to tune them.
        "pr": {"enabled": False, "bg": 96, "fg": 255},
        "limits": {
            "enabled": False,
            "fg": 255,
            "show_reset": True,  # time left until the window resets, e.g. "(2h14m)"
            "thresholds": [70, 90],  # usage % where the warn and crit colors start
            "colors": {"ok": 28, "warn": 166, "crit": 160},
        },
        "lines": {"enabled": False, "bg": 236, "fg": 250, "hide_zero": True},
        "session": {"enabled": False, "bg": 240, "fg": 255, "max_length": 24},
        "mode": {"enabled": False, "bg": 236, "fg": 250},
        "thinking": {"enabled": False, "fg": 255, "colors": {"on": 22, "off": 239}},
        "cache": {
            "enabled": False,
            "fg": 255,
            "show_ttl": True,  # time left until the cached prefix goes cold, e.g. "(4m)"
            "colors": {"warm": 22, "cold": 239},
        },
        "cost": {
            "enabled": False,
            "fg": 16,  # dark text: the amber/red status backgrounds are bright
            "hide_zero": True,
            "warn_threshold_usd": 5.0,
            "colors": {"normal": 178, "warn": 160},
        },
        "duration": {
            "enabled": False,
            "fg": 255,
            "hide_zero": True,
            "bg": 240,
        },
    },
}


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return copy.deepcopy(DEFAULT_CONFIG)
    with open(CONFIG_PATH, encoding="utf-8") as f:
        data = json.load(f)
    merged = copy.deepcopy(DEFAULT_CONFIG)
    _deep_merge(merged, data)
    return merged


def save_config(config: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _deep_merge(base: dict, override: dict) -> None:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
