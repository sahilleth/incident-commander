"""Incident Commander — configuration."""

from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    # LLM — Groq (cloud) or Ollama / any OpenAI-compatible API
    llm_provider: Literal["groq", "ollama", "openai"] = "groq"
    groq_api_key: str = ""
    groq_api_key_fallback: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    ollama_model: str = "llama3.2"
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_model: str = ""  # overrides provider default when set

    incident_db_path: Path = Path("./data/incidents.db")

    # Kubernetes
    kubeconfig: str = ""
    kube_context: str = ""

    # Logs: loki (preferred) or kubectl (pod log tail)
    log_backend: Literal["loki", "kubectl"] = "kubectl"
    loki_url: str = "http://localhost:3100"

    # Metrics
    prometheus_url: str = "http://localhost:9090"
    # Defaults use kube-state-metrics (kube-prometheus-stack / setup-observability).
    # Override with http_requests_total queries if your app exports them.
    prom_error_rate_query: str = (
        "sum(rate(kube_pod_container_status_restarts_total"
        "{namespace=\"{namespace}\", pod=~\"{service}.*\"}[5m])) * 100"
    )
    prom_p99_latency_query: str = "vector(0)"
    prom_request_rate_query: str = (
        "count(kube_pod_info{namespace=\"{namespace}\", pod=~\"{service}.*\"})"
    )

    max_worker_iterations: int = 5
    worker_timeout_seconds: int = 120
    kubectl_timeout_seconds: int = 30

    verify_max_attempts: int = 5
    verify_interval_seconds: int = 15
    verify_max_error_count: int = 10

    deploy_lookback_minutes: int = 60

    # LLM cost estimation (USD per 1K tokens; 0 = use built-in model table)
    llm_input_price_per_1k: float = 0.0
    llm_output_price_per_1k: float = 0.0

    # API authentication (off when unset — safe default for local dev)
    api_auth_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "INCIDENT_COMMANDER_API_TOKEN",
            "API_AUTH_TOKEN",
        ),
    )
    alertmanager_webhook_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "INCIDENT_COMMANDER_ALERTMANAGER_WEBHOOK_TOKEN",
            "ALERTMANAGER_WEBHOOK_TOKEN",
        ),
    )
    alertmanager_webhook_header: str = Field(
        default="X-Webhook-Token",
        validation_alias=AliasChoices(
            "INCIDENT_COMMANDER_ALERTMANAGER_WEBHOOK_HEADER",
            "ALERTMANAGER_WEBHOOK_HEADER",
        ),
    )
    cors_allowed_origins: str = Field(
        default="",
        validation_alias=AliasChoices(
            "INCIDENT_COMMANDER_CORS_ALLOWED_ORIGINS",
            "CORS_ALLOWED_ORIGINS",
        ),
    )

    def resolved_cors_origins(self) -> list[str]:
        raw = self.cors_allowed_origins.strip()
        if not raw:
            return list(DEFAULT_CORS_ORIGINS)
        return [origin.strip() for origin in raw.split(",") if origin.strip()]

    def llm_uses_local_ollama(self) -> bool:
        if self.llm_provider == "ollama":
            return True
        return "11434" in self.llm_base_url or "ollama" in self.llm_base_url.lower()

    def llm_is_configured(self) -> bool:
        return self.llm_uses_local_ollama() or bool(self.resolved_llm_api_keys())

    def llm_provider_label(self) -> str:
        if self.llm_uses_local_ollama():
            return "ollama"
        if self.resolved_llm_api_keys():
            return "groq"
        return "none"

    def resolved_llm_api_keys(self) -> list[str]:
        keys: list[str] = []
        for raw in (self.groq_api_key, self.groq_api_key_fallback):
            key = raw.strip()
            if key and key not in keys:
                keys.append(key)
        return keys

    def resolved_llm_api_key(self) -> str:
        keys = self.resolved_llm_api_keys()
        return keys[0] if keys else ""

    def resolved_llm_model(self) -> str:
        if self.llm_model.strip():
            return self.llm_model.strip()
        if self.llm_uses_local_ollama():
            return self.ollama_model
        return self.groq_model


def get_settings() -> Settings:
    return Settings()
