"""OpenAI-compatible LLM client with Groq key failover and Ollama support."""

import logging
from typing import Any

from openai import APIStatusError, AsyncOpenAI

from incident_commander.config import Settings

logger = logging.getLogger(__name__)

_QUOTA_HINTS = (
    "rate limit",
    "rate_limit",
    "quota",
    "exhausted",
    "insufficient",
    "too many requests",
    "capacity",
)

# Backward-compatible alias
GroqClientPool = None  # set after class definition


def _is_quota_or_rate_limit(exc: Exception) -> bool:
    if isinstance(exc, APIStatusError):
        if exc.status_code in (429, 402, 503):
            return True
    msg = str(exc).lower()
    return any(hint in msg for hint in _QUOTA_HINTS)


def _normalize_openai_base_url(url: str) -> str:
    base = url.rstrip("/")
    if base.endswith("/v1"):
        return base
    return f"{base}/v1"


class LLMClientPool:
    """Chat completions via Groq, Ollama, or any OpenAI-compatible API."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._clients: list[AsyncOpenAI] = []
        self._active_index = 0

        if settings.llm_uses_local_ollama():
            self._clients.append(
                AsyncOpenAI(
                    api_key="ollama",
                    base_url=_normalize_openai_base_url(settings.llm_base_url),
                )
            )
        else:
            for key in settings.resolved_llm_api_keys():
                self._clients.append(
                    AsyncOpenAI(
                        api_key=key,
                        base_url=_normalize_openai_base_url(settings.llm_base_url),
                    )
                )

    def has_client(self) -> bool:
        return len(self._clients) > 0

    @property
    def key_count(self) -> int:
        return len(self._clients)

    async def chat_completion(self, **kwargs: Any) -> Any:
        if not self._clients:
            raise RuntimeError("No LLM API keys configured")

        allow_failover = not self.settings.llm_uses_local_ollama()
        last_exc: Exception | None = None

        for attempt in range(len(self._clients)):
            idx = (self._active_index + attempt) % len(self._clients)
            client = self._clients[idx]
            try:
                result = await client.chat.completions.create(**kwargs)
                self._active_index = idx
                if attempt > 0:
                    logger.info("LLM request succeeded with fallback API key #%d", idx + 1)
                return result
            except Exception as exc:
                last_exc = exc
                if (
                    allow_failover
                    and _is_quota_or_rate_limit(exc)
                    and attempt < len(self._clients) - 1
                ):
                    logger.warning(
                        "LLM key #%d rate-limited (%s); trying next key",
                        idx + 1,
                        exc,
                    )
                    continue
                raise

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("No LLM configured")


GroqClientPool = LLMClientPool
