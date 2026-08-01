"""Postmortem export tests."""

from datetime import datetime, timezone

from incident_commander.export.postmortem import export_postmortem_markdown
from incident_commander.models.incident import Incident, IncidentStatus, TimelineEvent


def test_export_postmortem_contains_sections() -> None:
    incident = Incident(
        incident_id="INC-TEST",
        status=IncidentStatus.INVESTIGATING,
        opened_at=datetime.now(timezone.utc),
        trigger="test",
        service="payment-api",
        namespace="default",
        summary="Test incident summary",
        timeline=[
            TimelineEvent(
                id="e1",
                at=datetime.now(timezone.utc),
                source="logs_worker",
                event="ERROR: something failed",
            ),
        ],
    )
    md = export_postmortem_markdown(incident)
    assert "# Post-incident report: INC-TEST" in md
    assert "## Timeline" in md
    assert "payment-api" in md
    assert "ERROR: something failed" in md
