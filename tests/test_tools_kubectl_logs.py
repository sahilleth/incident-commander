"""Unit tests for kubectl-based logs client."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from incident_commander.config import Settings
from incident_commander.tools.clients import PodStatus
from incident_commander.tools.kubectl import Kubectl, KubectlError
from incident_commander.tools.kubectl_logs import KubectlLogsClient
from incident_commander.tools.kubernetes import KubernetesClient


@pytest.fixture
def kubectl_logs(tmp_path):
    settings = Settings(incident_db_path=tmp_path / "logs.db")
    kubectl = Kubectl(settings)
    k8s = MagicMock(spec=KubernetesClient)
    k8s.pods_for_service = AsyncMock(
        return_value=[
            PodStatus(
                name="payment-api-pod-1",
                namespace="default",
                phase="Running",
                ready=True,
                restarts=0,
            )
        ]
    )
    return KubectlLogsClient(kubectl, k8s), kubectl, k8s


@pytest.mark.asyncio
async def test_top_error_patterns_from_kubectl_logs(kubectl_logs):
    client, kubectl, _ = kubectl_logs
    kubectl.run = AsyncMock(
        return_value="[pod] ERROR NullPointerException in PaymentValidator\n"
        "[pod] ERROR NullPointerException in PaymentValidator\n"
    )

    patterns = await client.top_error_patterns(
        "payment-api",
        datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc),
        "default",
        limit=5,
    )

    assert len(patterns) == 1
    assert patterns[0].count == 2
    assert "NullPointerException" in patterns[0].message


@pytest.mark.asyncio
async def test_top_error_patterns_skips_kubectl_errors(kubectl_logs):
    client, kubectl, k8s = kubectl_logs
    k8s.pods_for_service = AsyncMock(
        return_value=[
            PodStatus(name="pod-a", namespace="default", phase="Running", ready=True, restarts=0),
            PodStatus(name="pod-b", namespace="default", phase="Running", ready=True, restarts=0),
        ]
    )

    async def run_side_effect(args):
        if "pod-a" in args:
            raise KubectlError("logs failed", returncode=1)
        return "[pod] ERROR connection reset by peer\n"

    kubectl.run = AsyncMock(side_effect=run_side_effect)

    patterns = await client.top_error_patterns(
        "payment-api",
        datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc),
        "default",
    )

    assert len(patterns) == 1
    assert "connection reset" in patterns[0].message


@pytest.mark.asyncio
async def test_top_error_patterns_no_pods_returns_empty(kubectl_logs):
    client, _, k8s = kubectl_logs
    k8s.pods_for_service = AsyncMock(return_value=[])

    patterns = await client.top_error_patterns(
        "payment-api",
        datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc),
        "default",
    )

    assert patterns == []
