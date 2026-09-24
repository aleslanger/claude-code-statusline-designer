import copy

import pytest

from claude_style import schemes
from claude_style.config import DEFAULT_CONFIG


@pytest.fixture
def schemes_dir(tmp_path, monkeypatch):
    target = tmp_path / "schemes"
    monkeypatch.setattr(schemes, "SCHEMES_DIR", target)
    return target


@pytest.fixture
def config():
    return copy.deepcopy(DEFAULT_CONFIG)
