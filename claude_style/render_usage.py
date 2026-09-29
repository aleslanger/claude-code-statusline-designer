"""Bash for the segments that report usage: plan limits, lines changed and the open pull request.

jq passes on only numbers (`numbers`) for every value that reaches bash
arithmetic, and the review state only selects a glyph, so nothing from the
session JSON is ever evaluated or printed unchecked.
"""
from __future__ import annotations

# rate_limits key -> label; a window Claude Code doesn't send is skipped.
LIMIT_WINDOWS = (("five_hour", "5h"), ("seven_day", "7d"), ("spend_limit", "spend"))

PR_STATE_GLYPHS = {
    "approved": "$G_PR_APPROVED",
    "changes_requested": "$G_PR_CHANGES",
    "pending": "$G_PR_PENDING",
    "draft": "$G_PR_DRAFT",
}

# Shared by every segment that counts down; emitted once, see needs_clock().
FMT_LEFT = """now=$(date +%s)
# $1 = seconds -> "3d4h", "2h14m" or "45m"
fmt_left() {
  local s=$1
  if [ "$s" -ge 86400 ]; then printf '%dd%dh' $((s / 86400)) $((s % 86400 / 3600))
  elif [ "$s" -ge 3600 ]; then printf '%dh%dm' $((s / 3600)) $((s % 3600 / 60))
  else printf '%dm' $((s / 60)); fi
}"""


def needs_clock(segments: dict) -> bool:
    limits, cache = segments["limits"], segments["cache"]
    return (limits["enabled"] and limits["show_reset"]) or (cache["enabled"] and cache["show_ttl"])


def draw(color: str, fg: int, text: str, args: str, powerline: bool) -> list[str]:
    """Draw one segment: `color` is its background in powerline mode, its text color in plain mode."""
    if powerline:
        return [f'  sep "$prev" {color}', f"  fg {fg}", f"  printf ' {text} ' {args}", f"  prev={color}"]
    return ["  plain_join", f"  fg {color}; printf '{text}' {args}; printf \"$RESET\""]


def limits_segment(limits: dict, powerline: bool) -> list[str]:
    warn, crit = limits["thresholds"]
    colors = limits["colors"]
    lines = [
        "# $1 = rate_limits key, $2 = label",
        "limit_window() {",
        '  local pct at left=""',
        '  pct=$(echo "$input" | jq -r ".rate_limits.$1.used_percentage | numbers | . + 0.5 | floor")',
        '  [ -n "$pct" ] || return 0',
    ]
    if limits["show_reset"]:
        lines += [
            '  at=$(echo "$input" | jq -r ".rate_limits.$1.resets_at | numbers | floor")',
            '  if [ -n "$at" ] && [ "$at" -gt "$now" ]; then left=" ($(fmt_left $((at - now))))"; fi',
        ]
    lines += [
        f'  if [ "$pct" -ge {crit} ]; then C_LIM={colors["crit"]}',
        f'  elif [ "$pct" -ge {warn} ]; then C_LIM={colors["warn"]}',
        f'  else C_LIM={colors["ok"]}; fi',
        *draw('"$C_LIM"', limits["fg"], "%s %d%%%s", '"$2" "$pct" "$left"', powerline),
        "}",
    ]
    return lines + [f"limit_window {key} {label}" for key, label in LIMIT_WINDOWS]


def lines_segment(seg: dict, powerline: bool) -> list[str]:
    guard = '[ "$lines_added" -gt 0 ] || [ "$lines_removed" -gt 0 ]' if seg["hide_zero"] else "true"
    return [
        "lines_added=$(echo \"$input\" | jq -r '(.cost.total_lines_added | numbers | floor) // 0')",
        "lines_removed=$(echo \"$input\" | jq -r '(.cost.total_lines_removed | numbers | floor) // 0')",
        f"if {guard}; then",
        *draw(str(seg["bg"]), seg["fg"], "+%d -%d", '"$lines_added" "$lines_removed"', powerline),
        "fi",
    ]


def pr_segment(seg: dict, powerline: bool) -> list[str]:
    cases = [f'  {state}) pr_glyph=" {glyph}" ;;' for state, glyph in PR_STATE_GLYPHS.items()]
    return [
        "pr_number=$(echo \"$input\" | jq -r '.pr.number | numbers | floor')",
        'if [ -n "$pr_number" ]; then',
        '  pr_prefix="#"  # GitLab merge requests are !N',
        "  [ \"$(echo \"$input\" | jq -r '.pr.kind // empty')\" = \"mr\" ] && pr_prefix=\"!\"",
        "  pr_glyph=\"\"",
        "  case \"$(echo \"$input\" | jq -r '.pr.review_state // empty')\" in",
        *cases,
        "  esac",
        *draw(str(seg["bg"]), seg["fg"], "%s%d%s", '"$pr_prefix" "$pr_number" "$pr_glyph"', powerline),
        "fi",
    ]
