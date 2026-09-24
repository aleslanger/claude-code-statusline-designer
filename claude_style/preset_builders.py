"""Small constructors that keep preset definitions to a few readable lines each.

Every preset must pass claude_style.contrast.readability_issues (enforced by
tests/test_presets.py): text vs. its background >= 3:1 (WCAG AA for UI).
"""
from __future__ import annotations


def seg(bg: int, fg: int, enabled: bool = True) -> dict:
    return {"enabled": enabled, "bg": bg, "fg": fg}


def git(clean: int, dirty: int, fg: int) -> dict:
    return {"enabled": True, "bg_clean": clean, "bg_dirty": dirty, "fg": fg}


def effort(fg: int, low: int, medium: int, high: int, xhigh: int, max_: int, default: int) -> dict:
    colors = {"low": low, "medium": medium, "high": high, "xhigh": xhigh, "max": max_, "default": default}
    return {"enabled": True, "fg": fg, "colors": colors}


def context(
    fg: int,
    thresholds: tuple[int, int, int],
    bar_bg: int,
    bar_empty: int,
    gradient_peak: int,
    style: str = "bar",
) -> dict:
    """thresholds: colors used below 60%, 85% and up to 100% context usage."""
    low, mid, high = thresholds
    return {
        "enabled": True,
        "fg": fg,
        "style": style,
        "thresholds": [[60, low], [85, mid], [101, high]],
        "bar_bg": bar_bg,
        "bar_empty": bar_empty,
        "gradient_peak": gradient_peak,
    }


def cost(fg: int, normal: int, warn: int) -> dict:
    return {"fg": fg, "colors": {"normal": normal, "warn": warn}}


def extras(output_style: tuple[int, int], cost_: dict, duration: tuple[int, int]) -> dict:
    """Colors for the off-by-default segments: (bg, fg) pairs plus a cost() spec."""
    return {
        "output_style": {"bg": output_style[0], "fg": output_style[1]},
        "cost": cost_,
        "duration": {"bg": duration[0], "fg": duration[1]},
    }


def preset(name: str, separator: str, segments: dict, extra: dict | None = None) -> dict:
    return {"preset": name, "separator": separator, "segments": {**segments, **(extra or {})}}
