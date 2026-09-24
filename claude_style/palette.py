"""xterm 256-color palette helpers: code <-> RGB, hex parsing, contrast."""
import re

HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")
CUBE_START = 16  # 16-231: 6x6x6 color cube
GRAY_START = 232  # 232-255: 24-step grayscale ramp
CUBE_LEVELS = (0, 95, 135, 175, 215, 255)
GRAY_BASE = 8
GRAY_STEP = 10
# The 16 system colors are whatever the terminal theme says; these are the xterm defaults.
SYSTEM_RGB = (
    (0, 0, 0), (205, 0, 0), (0, 205, 0), (205, 205, 0),
    (0, 0, 238), (205, 0, 205), (0, 205, 205), (229, 229, 229),
    (127, 127, 127), (255, 0, 0), (0, 255, 0), (255, 255, 0),
    (92, 92, 255), (255, 0, 255), (0, 255, 255), (255, 255, 255),
)
LIGHT_LUMINANCE = 140  # above this, dark text reads better than white
BLACK = 16
WHITE = 231


def xterm_rgb(code: int) -> tuple[int, int, int]:
    if code < CUBE_START:
        return SYSTEM_RGB[code]
    if code < GRAY_START:
        n = code - CUBE_START
        return CUBE_LEVELS[n // 36], CUBE_LEVELS[(n // 6) % 6], CUBE_LEVELS[n % 6]
    level = GRAY_BASE + (code - GRAY_START) * GRAY_STEP
    return level, level, level


def contrast_fg(code: int) -> int:
    r, g, b = xterm_rgb(code)
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return BLACK if luminance > LIGHT_LUMINANCE else WHITE


def _linear(channel: int) -> float:
    c = channel / 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(code: int) -> float:
    """WCAG 2.x relative luminance of a 256-color code."""
    r, g, b = (_linear(c) for c in xterm_rgb(code))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: int, b: int) -> float:
    """WCAG contrast ratio between two codes, 1.0 (none) to 21.0 (black on white)."""
    hi, lo = sorted((relative_luminance(a), relative_luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def nearest_code(rgb: tuple[int, int, int]) -> int:
    """Closest cube/grayscale code; system colors 0-15 are skipped since themes remap them."""
    def distance(code: int) -> int:
        return sum((a - b) ** 2 for a, b in zip(xterm_rgb(code), rgb))

    return min(range(CUBE_START, 256), key=distance)


def to_hex(code: int) -> str:
    return "#{:02x}{:02x}{:02x}".format(*xterm_rgb(code))


def parse_color(text: str) -> int:
    """Accepts a 256-color code ("61") or a hex color ("#5e81ac", mapped to the nearest code)."""
    text = text.strip()
    if text.isdigit():
        code = int(text)
        if 0 <= code <= 255:
            return code
        raise ValueError(f"color code must be 0-255, got {code}")
    match = HEX_RE.match(text)
    if not match:
        raise ValueError(f"'{text}' is neither a 0-255 color code nor a #rrggbb hex color")
    hex_digits = match.group(1)
    rgb = tuple(int(hex_digits[i : i + 2], 16) for i in (0, 2, 4))
    return nearest_code(rgb)
