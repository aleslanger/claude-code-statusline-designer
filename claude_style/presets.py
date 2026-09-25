"""Built-in color presets: dark themes here, light variants in presets_light.

Colors are xterm 256-color codes. Status segments (effort, context, cost)
use the conventional green -> amber -> red progression in every theme.
"""
import copy

from claude_style.config import DEFAULT_CONFIG
from claude_style.preset_builders import context, cost, effort, extras, git, preset, seg
from claude_style.presets_light import LIGHT_PRESETS

DARK_BAR = {"bar_bg": 237, "bar_empty": 234, "gradient_peak": 255}

DARK_PRESETS = {
    "agnoster": copy.deepcopy(DEFAULT_CONFIG),
    "minimal": preset(
        "minimal",
        "plain",
        {
            "user_host": seg(0, 110, enabled=False),
            "dir": seg(0, 74),
            "git": git(71, 173, 71),
            "model": seg(0, 80),
            "effort": effort(176, 71, 179, 173, 167, 176, 245),
            "context": context(250, (71, 179, 167), 237, 234, 255, style="percent"),
        },
        extras((0, 176), cost(250, 179, 167), (0, 245)),
    ),
    "mono": preset(
        "mono",
        "powerline",
        {
            "user_host": seg(235, 250),
            "dir": seg(238, 255),
            "git": git(240, 244, 255),
            "model": seg(242, 255),
            "effort": effort(235, 246, 248, 250, 252, 255, 244),
            "context": context(255, (239, 242, 244), **DARK_BAR),
        },
        extras((241, 255), cost(235, 250, 255), (239, 255)),
    ),
    "neon": preset(
        "neon",
        "powerline",
        {
            "user_host": seg(55, 231),
            "dir": seg(27, 231),
            "git": git(46, 208, 16),
            "model": seg(201, 231),
            "effort": effort(16, 46, 226, 208, 196, 129, 244),
            "context": context(231, (28, 136, 196), **DARK_BAR),
        },
        extras((93, 231), cost(16, 226, 196), (57, 231)),
    ),
    "dracula": preset(
        "dracula",
        "powerline",
        {
            "user_host": seg(239, 255),
            "dir": seg(61, 255),
            "git": git(84, 215, 236),
            "model": seg(141, 236),
            "effort": effort(236, 84, 228, 215, 203, 212, 103),
            "context": context(255, (29, 166, 161), **DARK_BAR),
        },
        extras((212, 236), cost(236, 228, 203), (61, 255)),
    ),
    "nord": preset(
        "nord",
        "powerline",
        {
            "user_host": seg(59, 253),
            "dir": seg(67, 236),
            "git": git(150, 167, 236),
            "model": seg(110, 236),
            "effort": effort(236, 150, 222, 173, 167, 176, 102),
            "context": context(253, (29, 130, 131), **DARK_BAR),
        },
        extras((176, 236), cost(236, 222, 167), (60, 253)),
    ),
    "gruvbox": preset(
        "gruvbox",
        "powerline",
        {
            "user_host": seg(237, 223),
            "dir": seg(66, 230),
            "git": git(100, 124, 230),
            "model": seg(132, 230),
            "effort": effort(230, 100, 136, 166, 124, 132, 239),
            "context": context(230, (100, 136, 124), **DARK_BAR),
        },
        extras((96, 230), cost(230, 136, 124), (239, 223)),
    ),
    "solarized": preset(
        "solarized",
        "powerline",
        {
            "user_host": seg(235, 244),
            "dir": seg(234, 244),
            "git": git(64, 160, 230),
            "model": seg(33, 230),
            "effort": effort(230, 64, 100, 166, 160, 125, 240),
            "context": context(230, (64, 166, 160), 235, 238, 255),
        },
        extras((125, 230), cost(230, 100, 160), (240, 230)),
    ),
    "catppuccin": preset(  # Mocha
        "catppuccin",
        "powerline",
        {
            "user_host": seg(237, 189),
            "dir": seg(111, 234),
            "git": git(151, 216, 234),
            "model": seg(183, 234),
            "effort": effort(234, 151, 223, 216, 211, 147, 245),
            "context": context(189, (29, 130, 161), 236, 233, 255),
        },
        extras((147, 234), cost(234, 223, 211), (238, 189)),
    ),
    "tokyo-night": preset(
        "tokyo-night",
        "powerline",
        {
            "user_host": seg(236, 153),
            "dir": seg(111, 234),
            "git": git(149, 215, 234),
            "model": seg(141, 234),
            "effort": effort(234, 149, 179, 215, 211, 141, 103),
            "context": context(189, (29, 130, 161), 236, 232, 255),
        },
        extras((117, 234), cost(234, 179, 211), (60, 189)),
    ),
    "onedark": preset(
        "onedark",
        "powerline",
        {
            "user_host": seg(237, 249),
            "dir": seg(75, 235),
            "git": git(114, 173, 235),
            "model": seg(176, 235),
            "effort": effort(235, 114, 180, 173, 168, 176, 245),
            "context": context(255, (28, 130, 124), 237, 234, 255),
        },
        extras((73, 235), cost(235, 180, 168), (239, 249)),
    ),
}

# Each dark theme is followed by its light variant, so cycling ←/→ in the menu
# visits a theme's two flavours back to back.
PRESETS = {}
for _name, _dark in DARK_PRESETS.items():
    PRESETS[_name] = _dark
    PRESETS[f"{_name}-light"] = LIGHT_PRESETS[f"{_name}-light"]
