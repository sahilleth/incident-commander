"""Paths for packaged eval fixtures and other eval assets."""

from pathlib import Path


def default_fixtures_dir() -> Path:
    """Directory of built-in eval scenario JSON files (works from PyPI install)."""
    return Path(__file__).resolve().parent / "fixtures"
