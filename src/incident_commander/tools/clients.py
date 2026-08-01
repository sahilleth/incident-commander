"""Tool client interfaces and shared data types."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class DeployEvent:
    at: datetime
    service: str
    revision: str
    description: str
    source: str = "kubernetes"


@dataclass
class LogPattern:
    first_seen: datetime
    message: str
    count: int
    level: str = "error"


@dataclass
class PodStatus:
    name: str
    namespace: str
    phase: str
    ready: bool
    restarts: int
    reason: str | None = None
    revision: str | None = None


@dataclass
class MetricSnapshot:
    at: datetime
    error_rate_pct: float
    p99_latency_ms: float
    request_rate: float
    baseline_error_rate_pct: float = 0.5
    source: str = "prometheus"
    notes: str = ""


class DeployClient(ABC):
    @abstractmethod
    async def recent_deploys(
        self, service: str, since: datetime, namespace: str
    ) -> list[DeployEvent]:
        ...

    async def rollout_history_text(self, service: str, namespace: str) -> str:
        """Optional extended deploy signal from kubectl rollout history."""
        return ""


class LogsClient(ABC):
    @abstractmethod
    async def top_error_patterns(
        self, service: str, since: datetime, namespace: str, limit: int = 5
    ) -> list[LogPattern]:
        ...


class K8sClient(ABC):
    @abstractmethod
    async def pods_for_service(
        self, service: str, namespace: str
    ) -> list[PodStatus]:
        ...

    async def pods_by_label(
        self, label_selector: str, namespace: str
    ) -> list[PodStatus]:
        return []

    @abstractmethod
    async def recent_warning_events(
        self, namespace: str, since: datetime
    ) -> list[str]:
        ...

    @abstractmethod
    async def rollout_undo(self, service: str, namespace: str) -> str:
        ...

    @abstractmethod
    async def scale_deployment(self, service: str, namespace: str, replicas: int) -> str:
        ...


class MetricsClient(ABC):
    @abstractmethod
    async def snapshot(
        self, service: str, since: datetime, namespace: str = "default"
    ) -> MetricSnapshot | None:
        ...


@dataclass
class ToolClients:
    deploy: DeployClient
    logs: LogsClient
    k8s: K8sClient
    metrics: MetricsClient
