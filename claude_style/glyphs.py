"""Glyph sets for the generated statusline.

Every glyph is spelled as \\xHH UTF-8 bytes inside bash $'...' quoting: macOS
still ships bash 3.2, which understands \\x escapes there but not \\u ones
(a \\u escape printed the literal text "\\ue0b0" instead of an arrow).
"""
from __future__ import annotations

GLYPH_MODES = ("nerdfont", "unicode", "ascii")
DEFAULT_GLYPH_MODE = "nerdfont"

GLYPH_MODE_LABELS = {
    "nerdfont": "Nerd Font arrows and icons",
    "unicode": "plain Unicode, no Nerd Font needed",
    "ascii": "ASCII only, works everywhere",
}

# name -> bash ANSI-C quoted literal
GLYPHS = {
    "nerdfont": {
        "sep": r"$'\xee\x82\xb0'",  # U+E0B0 powerline arrow
        "branch": r"$'\xef\x90\x9c '",  # U+F41C git branch icon
        "dirty": r"$' \xc2\xb1'",  # ±
        "full": r"$'\xe2\x96\x88'",  # █
        "empty": r"$'\xe2\x96\x91'",  # ░
    },
    "unicode": {
        "sep": r"$'\xe2\x96\x8c'",  # ▌ flat segment edge
        "branch": r"$'\xe2\x8e\x87 '",  # ⎇
        "dirty": r"$' \xc2\xb1'",
        "full": r"$'\xe2\x96\x88'",
        "empty": r"$'\xe2\x96\x91'",
    },
    "ascii": {
        "sep": "''",
        "branch": "''",
        "dirty": "' *'",
        "full": "'#'",
        "empty": "'.'",
    },
}


def glyph_definitions(mode: str) -> str:
    """Bash assignments for the chosen glyph set (G_SEP, G_BRANCH, ...)."""
    return "\n".join(f"G_{name.upper()}={literal}" for name, literal in GLYPHS[mode].items())
