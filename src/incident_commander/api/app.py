"""FastAPI application."""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from incident_commander.config import get_settings
from incident_commander.orchestrator.commander import IncidentCommander
from incident_commander.state.store import IncidentStore


class OpenIncidentRequest(BaseModel):
    service: str
    trigger: str = "manual"
    severity: str = "SEV2"
    environment: str = "prod"
    namespace: str = "default"


class ApproveRequest(BaseModel):
    approval_id: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    store = IncidentStore(settings.incident_db_path)
    await store.init()
    app.state.settings = settings
    app.state.store = store
    app.state.commander = IncidentCommander(settings, store)
    yield


app = FastAPI(
    title="Incident Commander",
    description="Multi-agent incident orchestration API",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/incidents")
async def create_incident(body: OpenIncidentRequest) -> dict[str, Any]:
    commander: IncidentCommander = app.state.commander
    incident = await commander.open_incident(
        service=body.service,
        trigger=body.trigger,
        severity=body.severity,
        environment=body.environment,
        namespace=body.namespace,
    )
    return incident.model_dump(mode="json")


@app.get("/incidents/{incident_id}")
async def get_incident(incident_id: str) -> dict[str, Any]:
    store: IncidentStore = app.state.store
    incident = await store.get(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident.model_dump(mode="json")


@app.get("/incidents")
async def list_incidents() -> list[dict[str, Any]]:
    store: IncidentStore = app.state.store
    incidents = await store.list_recent()
    return [i.model_dump(mode="json") for i in incidents]


@app.post("/incidents/{incident_id}/investigate")
async def re_investigate(incident_id: str) -> dict[str, Any]:
    commander: IncidentCommander = app.state.commander
    incident = await commander.investigate(incident_id)
    return incident.model_dump(mode="json")


@app.post("/incidents/{incident_id}/approve")
async def approve(incident_id: str, body: ApproveRequest) -> dict[str, Any]:
    commander: IncidentCommander = app.state.commander
    incident = await commander.approve_action(incident_id, body.approval_id)
    return incident.model_dump(mode="json")
