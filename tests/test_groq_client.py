"""Tests for Groq API key failover."""

import pytest

from incident_commander.config import Settings
from incident_commander.llm.groq_client import GroqClientPool, _is_quota_or_rate_limit


def test_quota_detection_from_message() -> None:
    assert _is_quota_or_rate_limit(RuntimeError("rate limit exceeded"))


def test_resolved_llm_api_keys_dedupes() -> None:
    settings = Settings(
        groq_api_key="key-a",
        groq_api_key_fallback="key-b",
    )
    assert settings.resolved_llm_api_keys() == ["key-a", "key-b"]


def test_groq_pool_key_count() -> None:
    settings = Settings(groq_api_key="key-a", groq_api_key_fallback="key-b")
    pool = GroqClientPool(settings)
    assert pool.key_count == 2
