"""Drive the real claude-style menu in a pseudo-terminal and emulate its screen.

Shared by the end-to-end tests and scripts/make_screenshots.py. pyte rebuilds
the screen from curses' output, so callers see characters and their colors
exactly as a user would.
"""
from __future__ import annotations

import atexit
import fcntl
import os
import pty
import select
import shutil
import signal
import struct
import sys
import tempfile
import termios
import time
from pathlib import Path
from typing import ClassVar

import pyte

ROWS, COLS = 30, 100
DOWN, UP, RIGHT, LEFT = "\x1bOB", "\x1bOA", "\x1bOC", "\x1bOD"  # application-cursor-mode arrows, as curses enables them
ENTER, CTRL_C = "\r", "\x03"
QUIET_S = 0.25
POLL_S = 0.05
MAX_WAIT_S = 5.0
FAKE_USER, FAKE_HOST = "dev", "workstation"
SELECTED_MARK = "▸ "
MAX_ROWS_TO_SCAN = 40
PROJECT_ROOT = Path(__file__).resolve().parents[1]


class _Screen(pyte.Screen):
    """pyte lacks SU/SD (CSI S / CSI T), which ncurses uses to shift unchanged blocks."""

    def _scroll(self, count: int, to_row_attr: str, step) -> None:
        margins = self.margins or pyte.screens.Margins(0, self.lines - 1)
        saved_y = self.cursor.y
        self.cursor.y = getattr(margins, to_row_attr)
        for _ in range(max(1, count)):
            step()
        self.cursor.y = saved_y

    def scroll_up(self, count: int = 1, *_rest) -> None:
        self._scroll(count, "bottom", self.index)

    def scroll_down(self, count: int = 1, *_rest) -> None:
        self._scroll(count, "top", self.reverse_index)


class _Stream(pyte.ByteStream):
    csi: ClassVar[dict[str, str]] = {**pyte.ByteStream.csi, "S": "scroll_up", "T": "scroll_down"}


def fake_identity_bin(user: str = FAKE_USER, host: str = FAKE_HOST) -> Path:
    """A directory with `whoami`/`hostname` stand-ins, to prepend to PATH.

    Keeps output independent of the machine: CI runners have hostnames long
    enough to push the rest of the statusline off screen.
    """
    bin_dir = Path(tempfile.mkdtemp(prefix="claude-style-identity-"))
    atexit.register(shutil.rmtree, bin_dir, ignore_errors=True)
    for name, value in (("whoami", user), ("hostname", host)):
        tool = bin_dir / name
        tool.write_text(f"#!/bin/sh\necho {value}\n", encoding="utf-8")
        tool.chmod(0o755)
    return bin_dir


class TuiSession:
    def __init__(self, home: Path, rows: int = ROWS, cols: int = COLS, env: dict | None = None) -> None:
        self.screen = _Screen(cols, rows)
        self.stream = _Stream(self.screen)
        path = f"{fake_identity_bin()}{os.pathsep}{os.environ['PATH']}"
        self.pid, self.fd = pty.fork()
        if self.pid == 0:
            child_env = {
                **os.environ,
                "HOME": str(home),
                "PATH": path,
                "TERM": "xterm-256color",
                "COLORTERM": "",
                **(env or {}),
            }
            os.chdir(PROJECT_ROOT)
            os.execvpe(sys.executable, [sys.executable, "-m", "claude_style", "menu"], child_env)
        fcntl.ioctl(self.fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
        self.settle()

    def _pump(self, timeout: float) -> bool:
        """Feeds one chunk of output into the emulator. False when nothing arrived (or the program exited)."""
        ready, _, _ = select.select([self.fd], [], [], timeout)
        if not ready:
            return False
        try:
            chunk = os.read(self.fd, 65536)
        except OSError:
            return False
        if not chunk:
            return False
        self.stream.feed(chunk)
        return True

    def settle(self, max_wait: float = MAX_WAIT_S) -> None:
        """Feed output into the emulator until the program has been quiet for a moment."""
        deadline = time.time() + max_wait
        last_output = time.time()
        while time.time() < deadline and time.time() - last_output < QUIET_S:
            if self._pump(POLL_S):
                last_output = time.time()

    def wait_for(self, text: str, max_wait: float = MAX_WAIT_S) -> None:
        """Waits for `text` to appear on screen -- for long key sequences, where
        a quiet moment doesn't prove the program has caught up."""
        deadline = time.time() + max_wait
        while text not in self.screen_text():
            if time.time() > deadline:
                raise AssertionError(f"{text!r} never appeared:\n{self.screen_text()}")
            self._pump(POLL_S)
        self.settle()

    def send(self, keys: str, max_wait: float = MAX_WAIT_S) -> None:
        os.write(self.fd, keys.encode())
        self.settle(max_wait)

    def selected_line(self) -> str:
        return next((line for line in self.screen.display if SELECTED_MARK in line), "")

    def select_row(self, text: str) -> None:
        """Moves the menu cursor down until the highlighted row contains `text`."""
        for _ in range(MAX_ROWS_TO_SCAN):
            if text in self.selected_line():
                return
            self.send(DOWN)
        raise AssertionError(f"no menu row containing {text!r}")

    def screen_text(self) -> str:
        return "\n".join(self.screen.display)

    def row_containing(self, text: str) -> int:
        for y, line in enumerate(self.screen.display):
            if text in line:
                return y
        raise AssertionError(f"{text!r} not on screen:\n" + "\n".join(self.screen.display))

    def preview_row(self) -> int:
        return self.row_containing("LIVE PREVIEW") + 1

    def bg_of(self, y: int, text: str) -> str:
        x = self.screen.display[y].index(text)
        return self.screen.buffer[y][x].bg

    def finish(self) -> int:
        try:
            _, status = os.waitpid(self.pid, 0)
        finally:
            os.close(self.fd)
        return os.waitstatus_to_exitcode(status)

    def kill(self) -> None:
        try:
            os.kill(self.pid, signal.SIGKILL)
            os.waitpid(self.pid, 0)
        except (ProcessLookupError, ChildProcessError):
            pass
