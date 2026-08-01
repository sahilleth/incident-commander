"""Shared pytest fixtures."""

import pytest

from incident_commander.config import Settings


@pytest.fixture
def heuristic_settings(tmp_path) -> Settings:
    """Settings without Groq — fast, deterministic tests."""
    return Settings(
        incident_db_path=tmp_path / "test.db",
        groq_api_key="",
        verify_max_attempts=1,
        verify_interval_seconds=0,
    )
