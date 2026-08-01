"""Mitigation verifier tests."""

import pytest

from incident_commander.orchestrator.verifier import MitigationVerifier
from tests.fakes import fake_tool_clients


@pytest.mark.asyncio
async def test_verifier_passes_healthy_pods(heuristic_settings):
    from datetime import datetime, timezone

    from incident_commander.models.incident import Incident, IncidentStatus

    settings = heuristic_settings
    verifier = MitigationVerifier(settings, fake_tool_clients())
    incident = Incident(
        incident_id="INC-TEST",
        status=IncidentStatus.MITIGATING,
        opened_at=datetime.now(timezone.utc),
        trigger="test",
        service="payment-api",
        namespace="default",
    )
    result = await verifier.verify(incident)
    assert result.checks
    assert "pods_healthy" in {c.name for c in result.checks}
