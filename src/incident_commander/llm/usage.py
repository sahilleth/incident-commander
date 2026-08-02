"""Per-investigation LLM token usage tracking."""

from incident_commander.config import Settings
from incident_commander.models.incident import LLMUsage

_DEFAULT_PRICING: dict[str, tuple[float, float]] = {
    "llama-3.3-70b-versatile": (0.00059, 0.00079),
    "llama3.2": (0.0, 0.0),
    "default": (0.0005, 0.0005),
}


class LLMUsageAccumulator:
    """Request-scoped counter for one investigation (safe under concurrent serve)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self.estimated_cost_usd = 0.0

    def record(self, model: str, prompt_tokens: int, completion_tokens: int) -> None:
        self.calls += 1
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens
        self.total_tokens += prompt_tokens + completion_tokens
        input_rate, output_rate = self._pricing_per_1k(model)
        self.estimated_cost_usd += (
            (prompt_tokens / 1000.0) * input_rate + (completion_tokens / 1000.0) * output_rate
        )

    def snapshot(self) -> LLMUsage:
        return LLMUsage(
            calls=self.calls,
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
            total_tokens=self.total_tokens,
            estimated_cost_usd=round(self.estimated_cost_usd, 6),
        )

    def _pricing_per_1k(self, model: str) -> tuple[float, float]:
        if self.settings.llm_input_price_per_1k > 0 or self.settings.llm_output_price_per_1k > 0:
            return (
                self.settings.llm_input_price_per_1k,
                self.settings.llm_output_price_per_1k,
            )
        return _DEFAULT_PRICING.get(model, _DEFAULT_PRICING["default"])
