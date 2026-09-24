"""Light variants for terminals with a light background.

Pastel segments with dark text, a near-white bar background, and a toned-down
gradient peak so the yellow middle of the context bar stays visible on white.
"""
from claude_style.preset_builders import context, cost, effort, extras, git, preset, seg

LIGHT_BAR = {"bar_bg": 255, "bar_empty": 246, "gradient_peak": 175}

LIGHT_PRESETS = {
    "agnoster-light": preset(
        "agnoster-light",
        "powerline",
        {
            "user_host": seg(254, 238),
            "dir": seg(153, 17),
            "git": git(151, 223, 235),
            "model": seg(117, 17),
            "effort": effort(235, 151, 229, 223, 217, 183, 252),
            "context": context(235, (151, 229, 217), **LIGHT_BAR),
        },
        extras((225, 90), cost(235, 229, 217), (253, 238)),
    ),
    "minimal-light": preset(
        "minimal-light",
        "plain",
        {
            "user_host": seg(231, 24, enabled=False),
            "dir": seg(231, 25),
            "git": git(28, 130, 28),
            "model": seg(231, 30),
            "effort": effort(90, 28, 136, 130, 124, 90, 242),
            "context": context(238, (28, 136, 124), 255, 246, 175, style="percent"),
        },
        extras((231, 90), cost(238, 136, 124), (231, 240)),
    ),
    "mono-light": preset(
        "mono-light",
        "powerline",
        {
            "user_host": seg(254, 236),
            "dir": seg(252, 234),
            "git": git(250, 247, 233),
            "model": seg(248, 233),
            "effort": effort(233, 254, 252, 250, 248, 246, 253),
            "context": context(233, (255, 252, 249), 255, 244, 160),
        },
        extras((251, 234), cost(233, 252, 248), (253, 236)),
    ),
    "neon-light": preset(
        "neon-light",
        "powerline",
        {
            "user_host": seg(219, 53),
            "dir": seg(45, 17),
            "git": git(47, 214, 16),
            "model": seg(201, 231),
            "effort": effort(16, 47, 227, 214, 203, 177, 250),
            "context": context(16, (120, 227, 210), 255, 245, 175),
        },
        extras((213, 16), cost(16, 227, 210), (252, 16)),
    ),
    "dracula-light": preset(  # Dracula's official light variant is called Alucard
        "dracula-light",
        "powerline",
        {
            "user_host": seg(188, 235),
            "dir": seg(60, 231),
            "git": git(28, 130, 231),
            "model": seg(62, 231),
            "effort": effort(231, 28, 94, 130, 160, 125, 60),
            "context": context(235, (151, 223, 217), 254, 246, 170),
        },
        extras((125, 231), cost(235, 223, 217), (188, 235)),
    ),
    "nord-light": preset(  # Nord "Snow Storm" backgrounds with Frost/Aurora accents
        "nord-light",
        "powerline",
        {
            "user_host": seg(254, 236),
            "dir": seg(110, 236),
            "git": git(150, 216, 236),
            "model": seg(109, 236),
            "effort": effort(236, 150, 222, 216, 174, 182, 253),
            "context": context(236, (150, 222, 174), 255, 244, 170),
        },
        extras((182, 236), cost(236, 222, 174), (253, 236)),
    ),
    "gruvbox-light": preset(
        "gruvbox-light",
        "powerline",
        {
            "user_host": seg(223, 237),
            "dir": seg(109, 235),
            "git": git(143, 216, 235),
            "model": seg(175, 235),
            "effort": effort(235, 143, 179, 216, 174, 175, 187),
            "context": context(235, (143, 179, 174), 230, 244, 170),
        },
        extras((181, 235), cost(235, 179, 174), (187, 237)),
    ),
    "solarized-light": preset(
        "solarized-light",
        "powerline",
        {
            "user_host": seg(254, 241),
            "dir": seg(32, 230),
            "git": git(64, 166, 230),
            "model": seg(30, 230),
            "effort": effort(230, 64, 100, 166, 160, 125, 245),
            "context": context(235, (151, 229, 224), 254, 246, 170),
        },
        extras((125, 230), cost(235, 229, 224), (254, 241)),
    ),
}
