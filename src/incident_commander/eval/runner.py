"""Eval scenario models and replay runner."""

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from datetime import datetime, timezone

from incident_commander.config import Settings
from incident_commander.llm.synthesizer import HypothesisSynthesizer
from incident_commander.models.incident import (
    Incident,
    IncidentStatus,
    TimelineEvent,
)
from incident_commander.orchestrator.commander import IncidentCommander
from incident_commander.state.store import IncidentStore
from incident_commander.eval.fixture_clients import fixture_tool_clients


class EvalExpectation(BaseModel):
    top_hypothesis_contains: list[str] = Field(default_factory=list)
    min_contains_matches: int = 1
    min_confidence: float = 0.5
    should_request_rollback: bool = False
    should_not_auto_execute: bool = True


class EvalScenario(BaseModel):
    id: str
    description: str
    service: str = "payment-api"
    namespace: str = "default"
    trigger: str = "eval"
    timeline: list[TimelineEvent] = Field(default_factory=list)
    expectation: EvalExpectation = Field(default_factory=EvalExpectation)
    mode: str = "synthesizer"  # synthesizer | full


class EvalCaseResult(BaseModel):
    scenario_id: str
    passed: bool
    score: float
    details: list[str] = Field(default_factory=list)


class EvalReport(BaseModel):
    total: int
    passed: int
    failed: int
    results: list[EvalCaseResult] = Field(default_factory=list)


class EvalRunner:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.synthesizer = HypothesisSynthesizer(settings)

    async def run_scenario(self, scenario: EvalScenario) -> EvalCaseResult:
        if scenario.mode == "full":
            return await self._run_full(scenario)
        return await self._run_synthesizer(scenario)

    async def _run_synthesizer(self, scenario: EvalScenario) -> EvalCaseResult:
        incident = Incident(
            incident_id=f"EVAL-{scenario.id}",
            status=IncidentStatus.INVESTIGATING,
            opened_at=(
                scenario.timeline[0].at
                if scenario.timeline
                else datetime.now(timezone.utc)
            ),
            trigger=scenario.trigger,
            service=scenario.service,
            namespace=scenario.namespace,
            timeline=list(scenario.timeline),
        )
        hypotheses = await self.synthesizer.synthesize(incident)
        return self._score(scenario, hypotheses)

    async def _run_full(self, scenario: EvalScenario) -> EvalCaseResult:
        store = IncidentStore(Path(f"/tmp/eval-{scenario.id}.db"))
        await store.init()
        commander = IncidentCommander(self.settings, store)
        commander.clients = fixture_tool_clients()
        commander.runbook = __import__(
            "incident_commander.orchestrator.runbook",
            fromlist=["RunbookExecutor"],
        ).RunbookExecutor(commander.clients)

        incident = await commander.open_incident(
            service=scenario.service,
            trigger=scenario.trigger,
            namespace=scenario.namespace,
            dedupe_minutes=0,
        )
        # Merge fixture timeline if provided (simulates richer evidence)
        if scenario.timeline:
            incident.timeline = scenario.timeline + incident.timeline
            incident.hypotheses = await commander.synthesizer.synthesize(incident)
        return self._score(scenario, incident.hypotheses)

    def _score(
        self, scenario: EvalScenario, hypotheses: list
    ) -> EvalCaseResult:
        details: list[str] = []
        passed = True
        score = 0.0
        exp = scenario.expectation

        if not hypotheses:
            return EvalCaseResult(
                scenario_id=scenario.id,
                passed=False,
                score=0.0,
                details=["No hypotheses produced"],
            )

        top = hypotheses[0]
        details.append(f"Top: {top.id} ({top.confidence:.0%}) {top.description}")

        if top.confidence < exp.min_confidence:
            passed = False
            details.append(
                f"FAIL confidence {top.confidence:.0%} < {exp.min_confidence:.0%}"
            )
        else:
            score += 0.4

        matched = 0
        for needle in exp.top_hypothesis_contains:
            if needle.lower() in top.description.lower():
                matched += 1
                details.append(f"PASS contains '{needle}'")
            else:
                details.append(f"miss '{needle}'")

        if exp.top_hypothesis_contains:
            if matched < exp.min_contains_matches:
                passed = False
                details.append(
                    f"FAIL matched {matched}/{exp.min_contains_matches} required terms"
                )
            else:
                score += 0.3

        has_rollback = any(
            a.type == "rollback" for a in top.suggested_actions
        )
        if exp.should_request_rollback and not has_rollback:
            passed = False
            details.append("FAIL expected rollback action")
        elif exp.should_request_rollback:
            score += 0.3
            details.append("PASS rollback action suggested")

        score = min(1.0, score)
        return EvalCaseResult(
            scenario_id=scenario.id,
            passed=passed,
            score=score,
            details=details,
        )

    async def run_directory(self, fixtures_dir: Path) -> EvalReport:
        results: list[EvalCaseResult] = []
        for path in sorted(fixtures_dir.glob("*.json")):
            data = json.loads(path.read_text())
            scenario = EvalScenario.model_validate(data)
            results.append(await self.run_scenario(scenario))

        passed = sum(1 for r in results if r.passed)
        return EvalReport(
            total=len(results),
            passed=passed,
            failed=len(results) - passed,
            results=results,
        )

    async def record_incident(
        self, incident: Incident, out_path: Path, description: str = ""
    ) -> Path:
        scenario = EvalScenario(
            id=incident.incident_id.replace("INC-", ""),
            description=description or f"Recorded {incident.incident_id}",
            service=incident.service,
            namespace=incident.namespace,
            trigger=incident.trigger,
            timeline=incident.timeline,
            mode="synthesizer",
            expectation=EvalExpectation(
                top_hypothesis_contains=[],
                min_confidence=0.0,
            ),
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(scenario.model_dump(mode="json"), indent=2, default=str)
        )
        return out_path
