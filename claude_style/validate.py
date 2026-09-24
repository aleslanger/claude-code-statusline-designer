"""Config validation.

Every value in a config ends up interpolated into a generated bash script, so
anything that did not come from DEFAULT_CONFIG -- a hand-edited config.json or
an imported scheme file -- must pass through validate_config() before render.
"""
import re

from claude_style.config import COLOR_FIELDS, SEGMENT_ORDER, get_color

NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$")
COLOR_MIN = 0
COLOR_MAX = 255
SEPARATORS = ("powerline", "plain")
CONTEXT_STYLES = ("bar", "percent")
THRESHOLD_COUNT = 3
GRADIENT_PEAK_MIN = 100  # below this the gradient turns muddy brown on any background
THRESHOLD_LIMIT_MAX = 1000
COLS_MAX = 10000
PATH_SEGMENTS_MAX = 50
COST_MAX_USD = 1_000_000


class ConfigError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ConfigError(message)


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _require_int(value, lo: int, hi: int, where: str) -> None:
    _require(_is_int(value) and lo <= value <= hi, f"{where} must be an integer {lo}-{hi}, got {value!r}")


def _require_bool(value, where: str) -> None:
    _require(isinstance(value, bool), f"{where} must be true/false, got {value!r}")


def validate_name(name) -> None:
    _require(
        isinstance(name, str) and bool(NAME_RE.match(name)),
        f"invalid name {name!r}: use 1-40 letters, digits, '-' or '_', starting with a letter or digit",
    )


def _validate_colors(config: dict, segment: str) -> None:
    for path, _label in COLOR_FIELDS[segment]:
        where = f"segments.{segment}.{path}"
        try:
            value = get_color(config, segment, path)
        except (KeyError, IndexError, TypeError, ValueError):
            raise ConfigError(f"{where} is missing") from None
        _require_int(value, COLOR_MIN, COLOR_MAX, where)


def _validate_context(ctx: dict) -> None:
    _require(ctx.get("style") in CONTEXT_STYLES, f"segments.context.style must be one of {CONTEXT_STYLES}")
    _require_bool(ctx.get("true_color"), "segments.context.true_color")
    _require_int(ctx.get("gradient_peak"), GRADIENT_PEAK_MIN, COLOR_MAX, "segments.context.gradient_peak")
    thresholds = ctx.get("thresholds")
    _require(
        isinstance(thresholds, list) and len(thresholds) == THRESHOLD_COUNT,
        f"segments.context.thresholds must be a list of {THRESHOLD_COUNT} [limit, color] pairs",
    )
    for i, pair in enumerate(thresholds):
        _require(isinstance(pair, list) and len(pair) == 2, f"segments.context.thresholds.{i} must be [limit, color]")
        _require_int(pair[0], 0, THRESHOLD_LIMIT_MAX, f"segments.context.thresholds.{i}.0")


def _validate_dir(d: dict) -> None:
    _require_bool(d.get("responsive"), "segments.dir.responsive")
    _require_int(d.get("narrow_cols"), 0, COLS_MAX, "segments.dir.narrow_cols")
    _require_int(d.get("medium_cols"), 0, COLS_MAX, "segments.dir.medium_cols")
    _require_int(d.get("medium_segments"), 1, PATH_SEGMENTS_MAX, "segments.dir.medium_segments")


def _validate_cost(c: dict) -> None:
    _require_bool(c.get("hide_zero"), "segments.cost.hide_zero")
    warn = c.get("warn_threshold_usd")
    _require(
        isinstance(warn, (int, float)) and not isinstance(warn, bool) and 0 <= warn <= COST_MAX_USD,
        f"segments.cost.warn_threshold_usd must be a number 0-{COST_MAX_USD}, got {warn!r}",
    )


def validate_config(config) -> None:
    _require(isinstance(config, dict), "config must be a JSON object")
    validate_name(config.get("preset"))
    if config.get("based_on") is not None:
        validate_name(config["based_on"])
    _require(config.get("separator") in SEPARATORS, f"separator must be one of {SEPARATORS}")
    segments = config.get("segments")
    _require(isinstance(segments, dict), "segments must be an object")

    for segment in SEGMENT_ORDER:
        _require(isinstance(segments.get(segment), dict), f"segments.{segment} is missing")
        _require_bool(segments[segment].get("enabled"), f"segments.{segment}.enabled")
        _validate_colors(config, segment)

    _validate_context(segments["context"])
    _validate_dir(segments["dir"])
    _validate_cost(segments["cost"])
    _require_bool(segments["duration"].get("hide_zero"), "segments.duration.hide_zero")
