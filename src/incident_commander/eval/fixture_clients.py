"""Fake tool clients for eval full-replay mode."""

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


class _FakeDeploy(DeployClient):
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
        return "REVISION  CHANGE-CAUSE\n42        deploy"


class _FakeLogs(LogsClient):
    async def top_error_patterns(self, service, since, namespace, limit=5):
        since = since if since.tzinfo else since.replace(tzinfo=timezone.utc)
        return [
            LogPattern(
                first_seen=since + timedelta(minutes=1),
                message="NullPointerException in PaymentValidator",
                count=100,
                level="error",
            )
        ]


class _FakeK8s(K8sClient):
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
        return f"rollout undo deployment/{service} succeeded"


class _FakeMetrics(MetricsClient):
    async def snapshot(self, service, since, namespace="default"):
        return MetricSnapshot(
            at=datetime.now(timezone.utc),
            error_rate_pct=8.0,
            p99_latency_ms=900.0,
            request_rate=100.0,
            baseline_error_rate_pct=0.5,
        )


def fixture_tool_clients() -> ToolClients:
    return ToolClients(
        deploy=_FakeDeploy(),
        logs=_FakeLogs(),
        k8s=_FakeK8s(),
        metrics=_FakeMetrics(),
    )
