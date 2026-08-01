"""Incident Commander — configuration."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM (Groq by default — OpenAI-compatible API)
    groq_api_key: str = ""
    groq_api_key_fallback: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_model: str = ""  # falls back to groq_model when empty

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
        return self.llm_model.strip() or self.groq_model


def get_settings() -> Settings:
    return Settings()
