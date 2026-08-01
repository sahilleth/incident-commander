"""Groq / OpenAI-compatible client with API key failover."""

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


def _is_quota_or_rate_limit(exc: Exception) -> bool:
    if isinstance(exc, APIStatusError):
        if exc.status_code in (429, 402, 503):
            return True
    msg = str(exc).lower()
    return any(hint in msg for hint in _QUOTA_HINTS)


class GroqClientPool:
    """Try primary Groq key first; rotate to fallback on quota/rate-limit errors."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._clients: list[AsyncOpenAI] = []
        for key in settings.resolved_llm_api_keys():
            self._clients.append(
                AsyncOpenAI(api_key=key, base_url=settings.llm_base_url)
            )
        self._active_index = 0

    def has_client(self) -> bool:
        return len(self._clients) > 0

    @property
    def key_count(self) -> int:
        return len(self._clients)

    async def chat_completion(self, **kwargs: Any) -> Any:
        if not self._clients:
            raise RuntimeError("No LLM API keys configured")

        last_exc: Exception | None = None
        for attempt in range(len(self._clients)):
            idx = (self._active_index + attempt) % len(self._clients)
            client = self._clients[idx]
            try:
                result = await client.chat.completions.create(**kwargs)
                self._active_index = idx
                if attempt > 0:
                    logger.info(
                        "Groq request succeeded with fallback API key #%d",
                        idx + 1,
                    )
                return result
            except Exception as exc:
                last_exc = exc
                if _is_quota_or_rate_limit(exc) and attempt < len(self._clients) - 1:
                    logger.warning(
                        "Groq key #%d rate-limited or exhausted (%s); trying next key",
                        idx + 1,
                        exc,
                    )
                    continue
                raise

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("No LLM API keys configured")
