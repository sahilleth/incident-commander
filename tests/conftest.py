"""Shared pytest fixtures."""

import pytest
from httpx import ASGITransport, AsyncClient

from incident_commander.api.app import app
from incident_commander.config import Settings
from incident_commander.orchestrator.commander import IncidentCommander
from incident_commander.state.store import IncidentStore
from tests.fakes import fake_tool_clients


@pytest.fixture
def heuristic_settings(tmp_path) -> Settings:
    """Settings without Groq — fast, deterministic tests."""
    return Settings(
        incident_db_path=tmp_path / "test.db",
        groq_api_key="",
        groq_api_key_fallback="",
        verify_max_attempts=1,
        verify_interval_seconds=0,
    )


async def setup_app_state(
    settings: Settings,
    commander: IncidentCommander | None = None,
) -> IncidentCommander:
    store = IncidentStore(settings.incident_db_path)
    await store.init()
    if commander is None:
        commander = IncidentCommander(settings, store)
        commander.clients = fake_tool_clients()
    app.state.settings = settings
    app.state.store = store
    app.state.commander = commander
    return commander


@pytest.fixture
async def api_client(tmp_path):
    settings = Settings(
        incident_db_path=tmp_path / "api.db",
        groq_api_key="",
        groq_api_key_fallback="",
        verify_max_attempts=1,
        verify_interval_seconds=0,
    )
    await setup_app_state(settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, settings
