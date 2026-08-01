"""Domain models for incident state."""

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class IncidentStatus(StrEnum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    MITIGATING = "mitigating"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


class ActionRisk(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TimelineEvent(BaseModel):
    id: str
    at: datetime
    source: str
    event: str
    confidence: Literal["low", "medium", "high"] = "medium"
    metadata: dict[str, Any] = Field(default_factory=dict)


class SuggestedAction(BaseModel):
    type: str
    description: str
    risk: ActionRisk = ActionRisk.MEDIUM
    requires_approval: bool = True
    params: dict[str, Any] = Field(default_factory=dict)


class Hypothesis(BaseModel):
    id: str
    description: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_event_ids: list[str] = Field(default_factory=list)
    suggested_actions: list[SuggestedAction] = Field(default_factory=list)


class WorkerRun(BaseModel):
    worker: str
    status: Literal["pending", "running", "complete", "failed", "timeout"] = "pending"
    iterations: int = 0
    tools_called: list[str] = Field(default_factory=list)
    summary: str = ""
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class PendingApproval(BaseModel):
    id: str
    action: SuggestedAction
    hypothesis_id: str
    requested_at: datetime
    status: Literal["pending", "approved", "rejected"] = "pending"


class Incident(BaseModel):
    incident_id: str
    status: IncidentStatus = IncidentStatus.OPEN
    opened_at: datetime
    trigger: str
    service: str
    environment: str = "prod"
    severity: str = "SEV2"
    namespace: str = "default"

    timeline: list[TimelineEvent] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    worker_runs: list[WorkerRun] = Field(default_factory=list)
    approvals_pending: list[PendingApproval] = Field(default_factory=list)

    human_lead: str | None = None
    resolved_at: datetime | None = None
    summary: str = ""

    def add_timeline_event(
        self,
        event_id: str,
        at: datetime,
        source: str,
        event: str,
        confidence: Literal["low", "medium", "high"] = "medium",
        metadata: dict[str, Any] | None = None,
    ) -> TimelineEvent:
        entry = TimelineEvent(
            id=event_id,
            at=at,
            source=source,
            event=event,
            confidence=confidence,
            metadata=metadata or {},
        )
        self.timeline.append(entry)
        return entry


class WorkerResult(BaseModel):
    worker: str
    timeline_events: list[TimelineEvent] = Field(default_factory=list)
    summary: str = ""
    tools_called: list[str] = Field(default_factory=list)
    iterations: int = 0
    error: str | None = None
