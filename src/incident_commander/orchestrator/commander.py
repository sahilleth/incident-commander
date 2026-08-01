"""Incident Commander orchestrator (supervisor)."""

import asyncio
import uuid
from datetime import datetime, timezone

from incident_commander.config import Settings
from incident_commander.llm.synthesizer import HypothesisSynthesizer
from incident_commander.models.incident import (
    Incident,
    IncidentStatus,
    PendingApproval,
    TimelineEvent,
    WorkerRun,
)
from incident_commander.orchestrator.runbook import RunbookExecutor
from incident_commander.orchestrator.verifier import MitigationVerifier
from incident_commander.state.store import IncidentStore
from incident_commander.tools.factory import build_tool_clients
from incident_commander.workers.deploy import DeployCorrelatorWorker
from incident_commander.workers.k8s import K8sWorker
from incident_commander.workers.logs import LogsWorker
from incident_commander.workers.metrics import MetricsWorker


class IncidentCommander:
    DEFAULT_WORKERS = (
        DeployCorrelatorWorker,
        LogsWorker,
        K8sWorker,
        MetricsWorker,
    )

    def __init__(self, settings: Settings, store: IncidentStore) -> None:
        self.settings = settings
        self.store = store
        self.clients = build_tool_clients(settings)
        self.synthesizer = HypothesisSynthesizer(settings)
        self.runbook = RunbookExecutor(self.clients)
        self.verifier = MitigationVerifier(settings, self.clients)

    def _new_incident_id(self) -> str:
        now = datetime.now(timezone.utc)
        return f"INC-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

    async def open_incident(
        self,
        service: str,
        trigger: str,
        severity: str = "SEV2",
        environment: str = "prod",
        namespace: str = "default",
        dedupe_minutes: int = 15,
    ) -> Incident:
        existing = await self.store.list_open_for_service(service, dedupe_minutes)
        if existing:
            return existing[0]

        incident = Incident(
            incident_id=self._new_incident_id(),
            status=IncidentStatus.INVESTIGATING,
            opened_at=datetime.now(timezone.utc),
            trigger=trigger,
            service=service,
            environment=environment,
            severity=severity,
            namespace=namespace,
        )
        await self.store.save(incident)
        return await self.investigate(incident.incident_id)

    async def investigate(self, incident_id: str) -> Incident:
        incident = await self.store.get(incident_id)
        if incident is None:
            raise ValueError(f"Incident {incident_id} not found")

        incident.status = IncidentStatus.INVESTIGATING
        workers = [w(self.clients, self.settings) for w in self.DEFAULT_WORKERS]

        async def run_worker(worker):
            run = WorkerRun(
                worker=worker.name,
                status="running",
                started_at=datetime.now(timezone.utc),
            )
            incident.worker_runs.append(run)
            try:
                result = await asyncio.wait_for(
                    worker.run(incident),
                    timeout=self.settings.worker_timeout_seconds,
                )
                for event in result.timeline_events:
                    incident.timeline.append(event)
                run.status = "complete" if not result.error else "failed"
                run.iterations = result.iterations
                run.tools_called = result.tools_called
                run.summary = result.summary
                run.error = result.error
            except asyncio.TimeoutError:
                run.status = "timeout"
                run.error = "Worker timed out"
            except Exception as exc:
                run.status = "failed"
                run.error = str(exc)
            run.finished_at = datetime.now(timezone.utc)
            return run

        await asyncio.gather(*(run_worker(w) for w in workers))

        incident.hypotheses = await self.synthesizer.synthesize(incident)
        incident.approvals_pending = self._queue_approvals(incident)
        incident.summary = self._build_summary(incident)

        await self.store.save(incident)
        return incident

    def _queue_approvals(self, incident: Incident) -> list[PendingApproval]:
        pending: list[PendingApproval] = []
        if not incident.hypotheses:
            return pending

        top = incident.hypotheses[0]
        has_error_signals = self._timeline_has_error_signals(incident)

        for action in top.suggested_actions:
            if not action.requires_approval or action.risk.value not in ("medium", "high"):
                continue
            if action.type == "rollback" and not has_error_signals:
                continue
            if action.type == "rollback" and top.confidence < 0.55:
                continue
            pending.append(
                PendingApproval(
                    id=f"APR-{uuid.uuid4().hex[:8]}",
                    action=action,
                    hypothesis_id=top.id,
                    requested_at=datetime.now(timezone.utc),
                )
            )
        return pending

    def _timeline_has_error_signals(self, incident: Incident) -> bool:
        error_tokens = (
            "error",
            "exception",
            "crashloop",
            "failed",
            "oom",
            "5xx",
            "error rate",
        )
        for event in incident.timeline:
            text = event.event.lower()
            if event.source in ("logs_worker", "k8s_worker", "metrics_worker"):
                if any(token in text for token in error_tokens):
                    return True
            if event.source == "k8s_worker" and "unhealthy" in text:
                return True
        return False

    def _build_summary(self, incident: Incident) -> str:
        lines = [
            f"Incident {incident.incident_id} — {incident.service} ({incident.severity})",
            f"Trigger: {incident.trigger}",
            f"Status: {incident.status.value}",
            "",
            "Timeline:",
        ]
        for e in sorted(incident.timeline, key=self._timeline_sort_key):
            lines.append(f"  [{e.at.strftime('%H:%M:%S')}] {e.source}: {e.event}")

        if incident.hypotheses:
            lines.append("")
            lines.append("Hypotheses:")
            for h in incident.hypotheses:
                lines.append(f"  {h.id} ({h.confidence:.0%}): {h.description}")

        if incident.approvals_pending:
            lines.append("")
            lines.append("Pending approvals:")
            for a in incident.approvals_pending:
                lines.append(f"  - {a.action.type}: {a.action.description}")

        return "\n".join(lines)

    def _timeline_sort_key(self, event: TimelineEvent) -> datetime:
        at = event.at
        if at.tzinfo is None:
            return at.replace(tzinfo=timezone.utc)
        return at

    async def approve_action(self, incident_id: str, approval_id: str) -> Incident:
        incident = await self.store.get(incident_id)
        if incident is None:
            raise ValueError(f"Incident {incident_id} not found")

        matched = False
        for approval in incident.approvals_pending:
            if approval.id == approval_id:
                matched = True
                approval.status = "approved"
                incident.status = IncidentStatus.MITIGATING
                incident.add_timeline_event(
                    event_id=f"{incident_id}-approval-{approval_id}",
                    at=datetime.now(timezone.utc),
                    source="commander",
                    event=f"Approved action: {approval.action.type} — {approval.action.description}",
                    confidence="high",
                )
                try:
                    result = await self.runbook.execute(incident, approval.action)
                    incident.add_timeline_event(
                        event_id=f"{incident_id}-action-executed",
                        at=datetime.now(timezone.utc),
                        source="runbook_executor",
                        event=f"Executed {approval.action.type}: {result}",
                        confidence="high",
                        metadata=approval.action.params,
                    )

                    verification = await self.verifier.verify(incident)
                    for check in verification.checks:
                        incident.add_timeline_event(
                            event_id=f"{incident_id}-verify-{check.name}",
                            at=datetime.now(timezone.utc),
                            source="verifier",
                            event=f"Check {check.name}: {'PASS' if check.passed else 'FAIL'} — {check.detail}",
                            confidence="high" if check.passed else "medium",
                        )
                    incident.add_timeline_event(
                        event_id=f"{incident_id}-verify-summary",
                        at=datetime.now(timezone.utc),
                        source="verifier",
                        event=verification.summary,
                        confidence="high" if verification.verified else "low",
                    )

                    if verification.verified:
                        incident.status = IncidentStatus.RESOLVED
                        incident.resolved_at = datetime.now(timezone.utc)
                    else:
                        incident.status = IncidentStatus.ESCALATED
                except Exception as exc:
                    incident.add_timeline_event(
                        event_id=f"{incident_id}-action-failed",
                        at=datetime.now(timezone.utc),
                        source="runbook_executor",
                        event=f"Failed {approval.action.type}: {exc}",
                        confidence="high",
                    )
                    incident.status = IncidentStatus.ESCALATED
                incident.approvals_pending = [
                    a for a in incident.approvals_pending if a.id != approval_id
                ]
                incident.summary = self._build_summary(incident)
                break

        if not matched:
            raise ValueError(f"Approval {approval_id} not found or already processed")

        if incident.status in (IncidentStatus.RESOLVED, IncidentStatus.ESCALATED):
            incident.approvals_pending = []

        await self.store.save(incident)
        return incident
