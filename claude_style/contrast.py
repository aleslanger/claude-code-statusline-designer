"""Readability check: WCAG contrast of every text/background pair a config can draw."""
from __future__ import annotations

from typing import NamedTuple

from claude_style.palette import contrast_ratio

MIN_TEXT_CONTRAST = 3.0  # WCAG AA for UI components and large text
MIN_SUBTLE_CONTRAST = 1.4  # empty bar blocks are meant to be quiet, not invisible
DARK_TERMINAL_BG = 234
LIGHT_TERMINAL_BG = 231
SIMPLE_SEGMENTS = ("user_host", "dir", "model", "output_style", "duration")


class Issue(NamedTuple):
    segment: str
    what: str
    fg: int
    bg: int
    ratio: float
    minimum: float

    def describe(self) -> str:
        return f"{self.what} {self.ratio:.1f}:1 (needs {self.minimum:.1f})"


def _powerline_pairs(segments: dict) -> list[tuple[str, str, int, int, float]]:
    pairs = [(s, "text on background", segments[s]["fg"], segments[s]["bg"], MIN_TEXT_CONTRAST) for s in SIMPLE_SEGMENTS]
    git = segments["git"]
    pairs += [("git", f"text on {state} background", git["fg"], git[f"bg_{state}"], MIN_TEXT_CONTRAST) for state in ("clean", "dirty")]
    effort = segments["effort"]
    pairs += [("effort", f"text on '{level}'", effort["fg"], bg, MIN_TEXT_CONTRAST) for level, bg in effort["colors"].items()]
    cost = segments["cost"]
    pairs += [("cost", f"text on '{state}'", cost["fg"], bg, MIN_TEXT_CONTRAST) for state, bg in cost["colors"].items()]

    ctx = segments["context"]
    for limit, bg in ctx["thresholds"]:
        pairs.append(("context", f"text on <{limit}% background", ctx["fg"], bg, MIN_TEXT_CONTRAST))
        pairs.append(("context", f"empty blocks on <{limit}% background", ctx["bar_empty"], bg, MIN_SUBTLE_CONTRAST))
    if ctx["true_color"]:
        pairs.append(("context", "text on bar background", ctx["fg"], ctx["bar_bg"], MIN_TEXT_CONTRAST))
        pairs.append(("context", "empty blocks on bar background", ctx["bar_empty"], ctx["bar_bg"], MIN_SUBTLE_CONTRAST))
    return pairs


def _plain_pairs(segments: dict, terminal_bg: int) -> list[tuple[str, str, int, int, float]]:
    """In plain mode every color is a foreground on the terminal's own background."""
    drawn = [(s, "text", segments[s]["fg"]) for s in SIMPLE_SEGMENTS]
    drawn += [("git", f"{state} branch", segments["git"][f"bg_{state}"]) for state in ("clean", "dirty")]
    drawn += [("effort", f"'{level}'", c) for level, c in segments["effort"]["colors"].items()]
    drawn += [("cost", f"'{state}'", c) for state, c in segments["cost"]["colors"].items()]
    drawn += [("context", f"<{limit}% text", c) for limit, c in segments["context"]["thresholds"]]
    return [(seg, f"{what} on terminal background", fg, terminal_bg, MIN_TEXT_CONTRAST) for seg, what, fg in drawn]


def readability_issues(config: dict, terminal_bg: int | None = None) -> list[Issue]:
    """Pairs below their minimum contrast. Plain mode needs the terminal background to judge."""
    segments = config["segments"]
    if config["separator"] == "powerline":
        pairs = _powerline_pairs(segments)
    elif terminal_bg is not None:
        pairs = _plain_pairs(segments, terminal_bg)
    else:
        return []
    issues = []
    for segment, what, fg, bg, minimum in pairs:
        ratio = contrast_ratio(fg, bg)
        if ratio < minimum:
            issues.append(Issue(segment, what, fg, bg, ratio, minimum))
    return issues
