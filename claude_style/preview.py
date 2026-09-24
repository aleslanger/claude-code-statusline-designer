"""Render a config against sample session data for previewing in a real terminal.

Samples run inside a throwaway HOME holding two tiny git repos (one clean, one
with an untracked file), so the git segment and its clean/dirty colors show up
in every preview -- whether or not the user's own directories are repos.
"""
from __future__ import annotations

import atexit
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import NamedTuple

from claude_style.render import render

SCRIPT_NAME = "claude-style-preview"  # $0 for `bash -c`
SAMPLE_TIMEOUT_S = 5
SAMPLE_REPOS = {  # workdir -> (branch, has uncommitted changes)
    "projects/my-app": ("main", False),
    "projects/webapp": ("feature/login", True),
}

SAMPLES = [
    {
        "label": "clean repo, high effort, 25% context, $0.42, 12m",
        "workdir": "projects/my-app",
        "data": {
            "model": {"display_name": "Sonnet 5"},
            "context_window": {"used_percentage": 25},
            "effort": {"level": "high"},
            "cost": {"total_cost_usd": 0.42, "total_duration_ms": 12 * 60 * 1000},
            "session_id": "preview",
        },
    },
    {
        "label": "dirty repo, max effort, 90% context, $7.80, plan output style",
        "workdir": "projects/webapp",
        "data": {
            "model": {"display_name": "Opus 5"},
            "context_window": {"used_percentage": 90},
            "effort": {"level": "max"},
            "output_style": {"name": "plan"},
            "cost": {"total_cost_usd": 7.80, "total_duration_ms": 95 * 60 * 1000},
            "session_id": "preview",
        },
    },
    {
        "label": "no git, no effort field, no context/cost data (fresh session)",
        "workdir": "",
        "data": {
            "model": {"display_name": "Haiku"},
            "session_id": "preview",
        },
    },
]

_sample_home: Path | None = None


def _make_repo(path: Path, branch: str, dirty: bool) -> None:
    path.mkdir(parents=True)
    try:
        result = subprocess.run(["git", "init", "-q", "-b", branch, str(path)], capture_output=True, check=False)
    except FileNotFoundError:
        return  # no git installed: previews show no git segment, exactly as the real statusline would
    if result.returncode == 0 and dirty:
        (path / "login.py").write_text("", encoding="utf-8")


def sample_home() -> Path:
    """Throwaway HOME with the sample repos, created once per process and removed at exit."""
    global _sample_home
    if _sample_home is None:
        root = Path(tempfile.mkdtemp(prefix="claude-style-preview-"))
        atexit.register(shutil.rmtree, root, ignore_errors=True)
        for workdir, (branch, dirty) in SAMPLE_REPOS.items():
            _make_repo(root / workdir, branch, dirty)
        _sample_home = root
    return _sample_home


def _payload(sample: dict, home: Path) -> str:
    data = {**sample["data"], "workspace": {"current_dir": str(home / sample["workdir"])}}
    return json.dumps(data)


class SampleResult(NamedTuple):
    label: str
    output: str
    error: str  # empty when the script ran cleanly


def run_samples(config: dict, samples: list | None = None, columns: int | None = None) -> list[SampleResult]:
    """Runs the rendered statusline script against each sample, in parallel."""
    script = render(config)
    samples = SAMPLES if samples is None else samples
    home = sample_home()
    env = {**os.environ, "HOME": str(home)}
    if columns is not None:
        env["COLUMNS"] = str(columns)

    procs = []
    for sample in samples:
        proc = subprocess.Popen(
            ["bash", "-c", script, SCRIPT_NAME],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        procs.append((sample, proc))

    results = []
    for sample, proc in procs:
        try:
            out, err = proc.communicate(_payload(sample, home), timeout=SAMPLE_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            results.append(SampleResult(sample["label"], "", f"timed out after {SAMPLE_TIMEOUT_S}s"))
            continue
        error = err.strip() if proc.returncode != 0 else ""
        results.append(SampleResult(sample["label"], out.rstrip("\n"), error))
    return results


def preview(config: dict) -> None:
    for result in run_samples(config):
        print(f"\n\033[2m# {result.label}\033[0m")
        print(result.output)
        if result.error:
            print(f"\033[31mscript error: {result.error}\033[0m")
