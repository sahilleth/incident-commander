"""Base worker agent with ReAct support."""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone

from incident_commander.agents.react import ReActLoop, ReActResult
from incident_commander.config import Settings
from incident_commander.models.incident import Incident, WorkerResult
from incident_commander.tools.clients import ToolClients


class BaseWorker(ABC):
    name: str

    def __init__(self, clients: ToolClients, settings: Settings) -> None:
        self.clients = clients
        self.settings = settings
        self.react = ReActLoop(settings, self.name)

    @abstractmethod
    async def run(self, incident: Incident) -> WorkerResult:
        ...

    def _event_id(self, incident_id: str, suffix: str) -> str:
        return f"{incident_id}-{self.name}-{suffix}"

    def _since(
        self, incident: Incident, extra_minutes: int = 0
    ) -> datetime:
        since = incident.opened_at
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)
        if extra_minutes:
            since = since - timedelta(minutes=extra_minutes)
        return since

    def _to_worker_result(
        self,
        react_result: ReActResult,
        timeline_events: list,
        error: str | None = None,
    ) -> WorkerResult:
        return WorkerResult(
            worker=self.name,
            timeline_events=timeline_events,
            summary=react_result.summary,
            tools_called=react_result.tools_called,
            iterations=react_result.iterations,
            error=error or react_result.error,
        )
