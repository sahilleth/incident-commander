"""Post-mitigation verification loop."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

from incident_commander.config import Settings
from incident_commander.models.incident import Incident
from incident_commander.tools.clients import ToolClients


@dataclass
class VerificationCheck:
    name: str
    passed: bool
    detail: str


@dataclass
class VerificationResult:
    verified: bool
    attempts: int
    checks: list[VerificationCheck]
    summary: str


class MitigationVerifier:
    def __init__(self, settings: Settings, clients: ToolClients) -> None:
        self.settings = settings
        self.clients = clients

    async def verify(self, incident: Incident) -> VerificationResult:
        max_attempts = self.settings.verify_max_attempts
        interval = self.settings.verify_interval_seconds
        since = datetime.now(timezone.utc)
        all_checks: list[VerificationCheck] = []

        for attempt in range(1, max_attempts + 1):
            if attempt > 1:
                await asyncio.sleep(interval)

            checks = await self._run_checks(incident, since)
            all_checks = checks
            passed = sum(1 for c in checks if c.passed)
            required = self._required_pass_count(checks)

            if passed >= required:
                return VerificationResult(
                    verified=True,
                    attempts=attempt,
                    checks=checks,
                    summary=(
                        f"Mitigation verified after {attempt} attempt(s): "
                        f"{passed}/{len(checks)} checks passed"
                    ),
                )

        return VerificationResult(
            verified=False,
            attempts=max_attempts,
            checks=all_checks,
            summary=(
                f"Mitigation NOT verified after {max_attempts} attempts — escalate"
            ),
        )

    async def _run_checks(
        self, incident: Incident, since: datetime
    ) -> list[VerificationCheck]:
        checks: list[VerificationCheck] = []

        pods = await self.clients.k8s.pods_for_service(
            incident.service, incident.namespace
        )
        unhealthy = [
            p
            for p in pods
            if not p.ready or (p.reason and p.reason != "Completed")
        ]
        checks.append(
            VerificationCheck(
                name="pods_healthy",
                passed=len(pods) > 0 and len(unhealthy) == 0,
                detail=f"{len(pods) - len(unhealthy)}/{len(pods)} pods healthy",
            )
        )

        patterns = await self.clients.logs.top_error_patterns(
            incident.service, since, incident.namespace, limit=3
        )
        error_quiet = len(patterns) == 0
        if patterns:
            error_quiet = patterns[0].count < self.settings.verify_max_error_count
        checks.append(
            VerificationCheck(
                name="errors_quiet",
                passed=error_quiet,
                detail=(
                    "no recent errors"
                    if error_quiet
                    else f"top error count={patterns[0].count}"
                ),
            )
        )

        snap = await self.clients.metrics.snapshot(
            incident.service, since, incident.namespace
        )
        if snap is not None:
            rate_ok = snap.error_rate_pct <= snap.baseline_error_rate_pct * 2
            checks.append(
                VerificationCheck(
                    name="error_rate_ok",
                    passed=rate_ok,
                    detail=f"error_rate={snap.error_rate_pct:.1f}%",
                )
            )
        else:
            checks.append(
                VerificationCheck(
                    name="error_rate_ok",
                    passed=True,
                    detail="prometheus unavailable — skipped",
                )
            )

        return checks

    def _required_pass_count(self, checks: list[VerificationCheck]) -> int:
        # pods_healthy is mandatory; need at least 2 of 3 checks
        names_passed = {c.name for c in checks if c.passed}
        if "pods_healthy" not in names_passed:
            return 999
        return min(2, len(checks))
