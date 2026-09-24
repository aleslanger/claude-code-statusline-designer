.PHONY: install dev-install menu preview show presets uninstall reinstall clean lint format test docs dist

# Install the claude-style package (editable) so the CLI is on PATH.
install:
	pip install -e . --quiet

# Same, but also runs the interactive menu right after, for first-time setup.
dev-install: install
	claude-style menu

menu:
	claude-style menu

preview:
	claude-style preview

show:
	claude-style show

presets:
	claude-style presets

# Removes the statusLine entry from ~/.claude/settings.json and restores
# whatever statusline script was there before claude-style installed one.
uninstall:
	claude-style uninstall

# Re-apply the currently saved config to ~/.claude/statusline-command.sh.
reinstall:
	claude-style install

clean:
	find . -type d -name '__pycache__' -exec rm -rf {} +
	rm -rf *.egg-info build dist .ruff_cache .pytest_cache .coverage htmlcov

lint:
	ruff check claude_style tests scripts

test:
	python3 -m pytest --cov=claude_style --cov-report=term-missing

format:
	ruff format claude_style
	black claude_style

# Regenerate the README screenshots (docs/*.svg) from real output.
docs:
	python3 scripts/make_screenshots.py

# Build the sdist + wheel and validate their metadata (what PyPI will show).
dist:
	rm -rf dist
	python3 -m build
	python3 -m twine check --strict dist/*
