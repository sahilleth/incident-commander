"""Test doubles — used only in tests."""

from datetime import datetime, timedelta, timezone

from incident_commander.tools.clients import (
    DeployClient,
    DeployEvent,
    K8sClient,
    LogPattern,
    LogsClient,
    MetricSnapshot,
    MetricsClient,
    PodStatus,
    ToolClients,
)


class FakeDeployClient(DeployClient):
    async def recent_deploys(self, service, since, namespace):
        since = since if since.tzinfo else since.replace(tzinfo=timezone.utc)
        return [
            DeployEvent(
                at=since + timedelta(minutes=2),
                service=service,
                revision="42",
                description=f"Deployment {service} revision 42",
            )
        ]

    async def rollout_history_text(self, service, namespace):
        return "REVISION  CHANGE-CAUSE\n42"


class FakeLogsClient(LogsClient):
    last_since: datetime | None = None

    async def top_error_patterns(self, service, since, namespace, limit=5):
        FakeLogsClient.last_since = since
        since = since if since.tzinfo else since.replace(tzinfo=timezone.utc)
        return [
            LogPattern(
                first_seen=since + timedelta(minutes=2),
                message="NullPointerException in PaymentValidator.validate()",
                count=100,
                level="error",
            )
        ]


class FakeK8sClient(K8sClient):
    async def pods_for_service(self, service, namespace):
        return [
            PodStatus(
                name=f"{service}-pod-1",
                namespace=namespace,
                phase="Running",
                ready=False,
                restarts=3,
                reason="CrashLoopBackOff",
                revision="42",
            )
        ]

    async def pods_by_label(self, label_selector, namespace):
        return await self.pods_for_service("payment-api", namespace)

    async def recent_warning_events(self, namespace, since):
        return ["Readiness probe failed"]

    async def rollout_undo(self, service, namespace):
        return f"rollout undo deployment/{service} in {namespace} succeeded"

    async def scale_deployment(self, service, namespace, replicas):
        return f"scaled deployment/{service} in {namespace} to {replicas} replicas"


class FakeMetricsClient(MetricsClient):
    async def snapshot(self, service, since, namespace="default"):
        return MetricSnapshot(
            at=datetime.now(timezone.utc),
            error_rate_pct=8.0,
            p99_latency_ms=900.0,
            request_rate=100.0,
            baseline_error_rate_pct=0.5,
        )


def fake_tool_clients() -> ToolClients:
    return ToolClients(
        deploy=FakeDeployClient(),
        logs=FakeLogsClient(),
        k8s=FakeK8sClient(),
        metrics=FakeMetricsClient(),
    )
