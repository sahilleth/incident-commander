"""Tests for LLM client and Ollama configuration."""

from incident_commander.config import Settings
from incident_commander.llm.llm_client import LLMClientPool


def test_ollama_configured_without_groq_key() -> None:
    settings = Settings(
        llm_provider="ollama",
        llm_base_url="http://localhost:11434",
        groq_api_key="",
    )
    assert settings.llm_is_configured()
    assert settings.llm_uses_local_ollama()
    assert settings.resolved_llm_model() == "llama3.2"
    pool = LLMClientPool(settings)
    assert pool.has_client()
    assert pool.key_count == 1


def test_groq_keys_deduped() -> None:
    settings = Settings(groq_api_key="key-a", groq_api_key_fallback="key-b")
    assert settings.resolved_llm_api_keys() == ["key-a", "key-b"]
    pool = LLMClientPool(settings)
    assert pool.key_count == 2
