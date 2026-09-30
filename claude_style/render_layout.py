"""Bash that lays the collected segments out into one or more rows.

Segments don't draw their own edges. Each one starts with a marker,
\\037 previous-bg \\036 next-bg \\036 text-color \\037, and the whole line is
collected before anything is printed. layout() then measures every segment
and turns each marker into one of three things: a powerline arrow, a thin
divider (two equal backgrounds would otherwise melt into one block), or a row
break when the next segment would no longer fit into $COLUMNS.

Free text that reaches the line (session and agent names) has its control
characters stripped by jq, so it can't forge a marker.
"""
from __future__ import annotations

WRAP_MARGIN = 2  # columns Claude Code keeps around the status line
PLAIN_SEP_WIDTH = 3  # " | "

# Width in columns: SGR escapes removed, then one column per character. UTF-8
# continuation bytes are dropped under LC_ALL=C, so the count doesn't depend
# on the user's locale.
MEASURE = r"""# $1 = text with color escapes -> VW = its width in columns
vis_width() {
  local LC_ALL=C s=$1 head
  while [[ $s == *$'\033['* ]]; do
    head=${s%%$'\033['*}; s=${s#*$'\033['}; s=$head${s#*m}
  done
  s=${s//[$'\x80'-$'\xbf']/}
  VW=${#s}
}"""

POWERLINE_LAYOUT = r"""sep() { printf '\037%s\036%s\036%s\037' "$1" "$2" "$cur_fg"; }
sep_end() { printf '\037%s\036\036%s\037' "$1" "$cur_fg"; }
# Never starts a new row ("+" before the color): the effort stays next to its model.
sep_glued() { sep "$1" "+$2"; }
prev=""
vis_width "$G_SEP"; SEP_W=$VW

row_end() { fg "$1"; printf '\033[49m%s%s' "$G_SEP" "$RESET"; }

# $1 = the collected line -> L/N/F/G/T/W arrays: previous bg, own bg, divider color,
# glued (0/1), text and width of each segment; SEG_N = how many
split_segments() {
  local rest=${1#$'\037'} marker text
  SEG_N=0
  while [ -n "$rest" ]; do
    marker=${rest%%$'\037'*}; rest=${rest#*$'\037'}
    text=${rest%%$'\037'*}; rest=${rest:${#text}}; rest=${rest#$'\037'}
    L[SEG_N]=${marker%%$'\036'*}; marker=${marker#*$'\036'}
    N[SEG_N]=${marker%%$'\036'*}; F[SEG_N]=${marker#*$'\036'}
    G[SEG_N]=0
    case "${N[SEG_N]}" in +*) G[SEG_N]=1; N[SEG_N]=${N[SEG_N]#+} ;; esac
    T[SEG_N]=$text; vis_width "$text"; W[SEG_N]=$VW
    SEG_N=$(( SEG_N + 1 ))
  done
}

# $1 = the collected line -> rows joined by arrows, thin dividers and row breaks
layout() {
  local i j need row_w=0
  split_segments "$1"
  for (( i = 0; i < SEG_N; i++ )); do
    need=$(( W[i] + SEP_W )); j=$(( i + 1 ))
    while [ "$j" -lt "$SEG_N" ] && [ "${G[j]}" = 1 ]; do need=$(( need + W[j] + SEP_W )); j=$(( j + 1 )); done
    if [ -z "${N[i]}" ]; then row_end "${L[i]}"; return
    elif [ -z "${L[i]}" ]; then bg "${N[i]}"
    elif [ "${G[i]}" = 0 ] && [ "$wrap_cols" -gt 0 ] && [ $(( row_w + need )) -gt "$wrap_cols" ]; then
      row_end "${L[i]}"; printf '\n'; bg "${N[i]}"; row_w=0
    elif [ "${L[i]}" = "${N[i]}" ]; then fg "${F[i]}"; printf '%s' "$G_SEP_THIN"
    else fg "${L[i]}"; bg "${N[i]}"; printf '%s' "$G_SEP"
    fi
    printf '%s' "${T[i]}"
    row_w=$(( row_w + W[i] + SEP_W ))
  done
}"""

PLAIN_LAYOUT = rf"""plain_sep() {{ printf ' \033[34m|\033[0m '; }}
plain_join() {{ printf '\037\037'; }}

# $1 = the collected line -> rows joined by " | " and row breaks
layout() {{
  local rest=${{1#$'\037'}} text row_w=0
  while [ -n "$rest" ]; do
    rest=${{rest#*$'\037'}}
    text=${{rest%%$'\037'*}}; rest=${{rest:${{#text}}}}; rest=${{rest#$'\037'}}
    vis_width "$text"
    if [ "$row_w" -gt 0 ]; then
      if [ "$wrap_cols" -gt 0 ] && [ $(( row_w + {PLAIN_SEP_WIDTH} + VW )) -gt "$wrap_cols" ]; then
        printf '\n'; row_w=0
      else
        plain_sep; row_w=$(( row_w + {PLAIN_SEP_WIDTH} ))
      fi
    fi
    printf '%s' "$text"
    row_w=$(( row_w + VW ))
  done
}}"""


def _wrap_columns(wrap: bool) -> str:
    if not wrap:
        return "wrap_cols=0  # wrapping is off: one row, however long"
    return (
        "wrap_cols=0\n"
        f'case "${{COLUMNS:-}}" in ""|*[!0-9]*) ;; *) wrap_cols=$(( COLUMNS - {WRAP_MARGIN} )) ;; esac'
    )


def layout_helpers(powerline: bool, wrap: bool) -> str:
    """Helpers the segments call (sep / plain_join) plus the layout() that prints the rows."""
    layout = POWERLINE_LAYOUT if powerline else PLAIN_LAYOUT
    return "\n\n".join([MEASURE, _wrap_columns(wrap), layout])


def collect_and_print(body: list[str], powerline: bool) -> str:
    """Runs the segment code into $line, then lays it out."""
    closing = ['[ -n "$prev" ] && sep_end "$prev"'] if powerline else []
    return "\n".join(["line=$(", *body, *closing, ")", 'layout "$line"'])
