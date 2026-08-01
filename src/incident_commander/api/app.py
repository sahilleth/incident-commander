"""FastAPI application."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel

from incident_commander.api.alertmanager import parse_alertmanager_payload
from incident_commander.config import get_settings
from incident_commander.export.postmortem import export_postmortem_markdown
from incident_commander.orchestrator.commander import IncidentCommander
from incident_commander.state.store import IncidentStore

STATIC_DIR = Path(__file__).resolve().parent / "static"
REPO_ROOT = Path(__file__).resolve().parents[3]
FRONTEND_UI_DIRS = [
    REPO_ROOT / "frontendUI" / ".output" / "public",
    REPO_ROOT / "frontendUI" / "dist" / "client",
    REPO_ROOT / "frontendUI" / "dist",
]


class OpenIncidentRequest(BaseModel):
    service: str
    trigger: str = "manual"
    severity: str = "SEV2"
    environment: str = "prod"
    namespace: str = "default"


class ApproveRequest(BaseModel):
    approval_id: str


def _frontend_index() -> Path | None:
    for directory in FRONTEND_UI_DIRS:
        index = directory / "index.html"
        if index.is_file():
            return index
    return None


def _frontend_asset(path: str) -> Path | None:
    for directory in FRONTEND_UI_DIRS:
        candidate = directory / path
        if candidate.is_file():
            return candidate
    return None


def _wants_html(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    return "text/html" in accept and "application/json" not in accept


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
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = APIRouter()


@api.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@api.post("/incidents")
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


@api.get("/incidents/{incident_id}")
async def get_incident(incident_id: str, request: Request) -> Any:
    if _wants_html(request) and _frontend_index() is not None:
        return FileResponse(_frontend_index())

    store: IncidentStore = app.state.store
    incident = await store.get(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident.model_dump(mode="json")


@api.get("/incidents")
async def list_incidents(limit: int = 100) -> list[dict[str, Any]]:
    store: IncidentStore = app.state.store
    incidents = await store.list_recent(limit=limit)
    return [i.model_dump(mode="json") for i in incidents]


@api.get("/incidents/{incident_id}/postmortem.md")
async def get_postmortem(incident_id: str) -> PlainTextResponse:
    store: IncidentStore = app.state.store
    incident = await store.get(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return PlainTextResponse(
        export_postmortem_markdown(incident),
        media_type="text/markdown; charset=utf-8",
    )


@api.post("/incidents/{incident_id}/investigate")
async def re_investigate(incident_id: str) -> dict[str, Any]:
    commander: IncidentCommander = app.state.commander
    try:
        incident = await commander.investigate(incident_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return incident.model_dump(mode="json")


@api.post("/incidents/{incident_id}/approve")
async def approve(incident_id: str, body: ApproveRequest) -> dict[str, Any]:
    commander: IncidentCommander = app.state.commander
    try:
        incident = await commander.approve_action(incident_id, body.approval_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return incident.model_dump(mode="json")


app.include_router(api, prefix="/api")
# Backward-compatible root paths for scripts, curl examples, and Alertmanager.
app.include_router(api)


@app.post("/webhooks/alertmanager")
async def alertmanager_webhook(body: dict[str, Any]) -> dict[str, Any]:
    """Receive Prometheus Alertmanager notifications and open incidents."""
    commander: IncidentCommander = app.state.commander
    parsed = parse_alertmanager_payload(body)

    if not parsed:
        return {"opened": [], "message": "No firing alerts with a deployment/service label"}

    opened: list[dict[str, Any]] = []
    for alert in parsed:
        incident = await commander.open_incident(
            service=alert["service"],
            trigger=alert["trigger"],
            severity=alert["severity"],
            namespace=alert["namespace"],
        )
        opened.append(
            {
                "incident_id": incident.incident_id,
                "service": incident.service,
                "namespace": incident.namespace,
                "alertname": alert["alertname"],
                "status": incident.status.value,
            }
        )

    return {"opened": opened, "count": len(opened)}


@app.get("/")
async def root() -> FileResponse:
    ui = _frontend_index()
    if ui is not None:
        return FileResponse(ui)
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/ui")
async def ui() -> FileResponse:
    ui_index = _frontend_index()
    if ui_index is not None:
        return FileResponse(ui_index)
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/assets/{asset_path:path}")
async def frontend_assets(asset_path: str) -> FileResponse:
    asset = _frontend_asset(f"assets/{asset_path}")
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return FileResponse(asset)


@app.get("/{spa_path:path}")
async def spa_fallback(spa_path: str, request: Request) -> FileResponse:
    """Serve the React UI for client-side routes (e.g. /incidents/INC-...)."""
    if spa_path.startswith(("api/", "webhooks/", "docs", "openapi.json", "redoc")):
        raise HTTPException(status_code=404, detail="Not found")

    if spa_path.startswith("incidents/") and not _wants_html(request):
        raise HTTPException(status_code=404, detail="Not found")

    asset = _frontend_asset(spa_path)
    if asset is not None:
        return FileResponse(asset)

    ui = _frontend_index()
    if ui is not None:
        return FileResponse(ui)

    raise HTTPException(status_code=404, detail="Not found")
