"""Bash for the segments that describe the session: prompt cache, session name and active modes.

Session and agent names are free text, so jq strips control characters before
they reach the terminal (no smuggled escape sequences) and shortens them. The
vim mode is shown only when it is one of the values Claude Code documents.
"""
from __future__ import annotations

from claude_style.render_usage import draw

AGENT_NAME_MAX = 24
VIM_MODES = ("NORMAL", "INSERT", "VISUAL", '"VISUAL LINE"')


def _clean_text(max_length: int) -> str:
    """jq filter: a printable string of at most max_length characters, ending in $e when cut."""
    return (
        rf'strings | gsub("\\p{{Cc}}"; "") | select(length > 0)'
        rf" | if length > {max_length} then .[:{max_length} - ($e | length)] + $e else . end"
    )


def cache_segment(cache: dict, powerline: bool) -> list[str]:
    colors = cache["colors"]
    countdown = [
        "    cache_at=$(echo \"$input\" | jq -r '.prompt_cache.expires_at | numbers | floor')",
        '    if [ -n "$cache_at" ] && [ "$cache_at" -gt "$now" ]; then',
        '      cache_text="$cache_text ($(fmt_left $((cache_at - now))))"',
        "    fi",
    ]
    return [
        "cache_warm=$(echo \"$input\" | jq -r '.prompt_cache.warm | booleans')",
        'if [ -n "$cache_warm" ]; then',
        '  cache_text="cache"',
        "  cache_hit=$(echo \"$input\" | jq -r '.prompt_cache.hit_ratio | numbers | . * 100 + 0.5 | floor')",
        '  [ -n "$cache_hit" ] && cache_text="$cache_text ${cache_hit}%"',
        '  if [ "$cache_warm" = "true" ]; then',
        f"    C_CACHE={colors['warm']}",
        *(countdown if cache["show_ttl"] else []),
        f'  else C_CACHE={colors["cold"]}; cache_text="$cache_text cold"; fi',
        *draw('"$C_CACHE"', cache["fg"], "%s", '"$cache_text"', powerline),
        "fi",
    ]


def session_segment(seg: dict, powerline: bool) -> list[str]:
    name_filter = _clean_text(seg["max_length"])
    return [
        f"session_name=$(echo \"$input\" | jq -r --arg e \"$G_ELLIPSIS\" '.session_name | {name_filter}')",
        'if [ -n "$session_name" ]; then',
        *draw(str(seg["bg"]), seg["fg"], "%s", '"$session_name"', powerline),
        "fi",
    ]


def mode_segment(seg: dict, powerline: bool) -> list[str]:
    agent_filter = _clean_text(AGENT_NAME_MAX)
    return [
        'mode_text=""',
        'mode_add() { mode_text="${mode_text:+$mode_text }$1"; }',
        "[ \"$(echo \"$input\" | jq -r '.fast_mode // false')\" = \"true\" ] && mode_add fast",
        "vim_mode=$(echo \"$input\" | jq -r '.vim.mode // empty')",
        f'case "$vim_mode" in {"|".join(VIM_MODES)}) mode_add "$vim_mode" ;; esac',
        f"agent_name=$(echo \"$input\" | jq -r --arg e \"$G_ELLIPSIS\" '.agent.name | {agent_filter}')",
        '[ -n "$agent_name" ] && mode_add "@$agent_name"',
        'if [ -n "$mode_text" ]; then',
        *draw(str(seg["bg"]), seg["fg"], "%s", '"$mode_text"', powerline),
        "fi",
    ]
