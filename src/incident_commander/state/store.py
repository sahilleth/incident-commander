"""SQLite persistence for incident state."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiosqlite

from incident_commander.models.incident import Incident


class IncidentStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    async def init(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS incidents (
                    incident_id TEXT PRIMARY KEY,
                    service TEXT NOT NULL,
                    status TEXT NOT NULL,
                    opened_at TEXT NOT NULL,
                    data JSON NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            await db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_incidents_service_status
                ON incidents (service, status)
                """
            )
            await db.commit()

    async def save(self, incident: Incident) -> None:
        now = datetime.now(timezone.utc).isoformat()
        payload = incident.model_dump(mode="json")
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO incidents (incident_id, service, status, opened_at, data, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(incident_id) DO UPDATE SET
                    service = excluded.service,
                    status = excluded.status,
                    opened_at = excluded.opened_at,
                    data = excluded.data,
                    updated_at = excluded.updated_at
                """,
                (
                    incident.incident_id,
                    incident.service,
                    incident.status.value,
                    incident.opened_at.isoformat(),
                    json.dumps(payload),
                    now,
                ),
            )
            await db.commit()

    async def get(self, incident_id: str) -> Incident | None:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT data FROM incidents WHERE incident_id = ?",
                (incident_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return Incident.model_validate(json.loads(row["data"]))

    async def list_open_for_service(
        self, service: str, within_minutes: int = 15
    ) -> list[Incident]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT data FROM incidents
                WHERE service = ? AND status NOT IN ('resolved', 'escalated')
                ORDER BY opened_at DESC
                """,
                (service,),
            )
            rows = await cursor.fetchall()
        incidents = [Incident.model_validate(json.loads(r["data"])) for r in rows]
        if not incidents:
            return []
        cutoff = datetime.now(timezone.utc)
        from datetime import timedelta

        window = timedelta(minutes=within_minutes)
        return [
            i
            for i in incidents
            if cutoff - i.opened_at.replace(tzinfo=timezone.utc) <= window
        ]

    async def list_recent(self, limit: int = 20) -> list[Incident]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT data FROM incidents ORDER BY opened_at DESC LIMIT ?",
                (limit,),
            )
            rows = await cursor.fetchall()
        return [Incident.model_validate(json.loads(r["data"])) for r in rows]
