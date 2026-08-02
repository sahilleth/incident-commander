"""Hypothesis synthesis — Groq (OpenAI-compatible) with heuristic fallback."""

import json
import logging
from dataclasses import dataclass
from typing import Any

from incident_commander.config import Settings
from incident_commander.llm.llm_client import LLMClientPool
from incident_commander.llm.usage import LLMUsageAccumulator
from incident_commander.models.incident import (
    ActionRisk,
    Hypothesis,
    Incident,
    SuggestedAction,
)

logger = logging.getLogger(__name__)

_SUBMIT_HYPOTHESES_TOOL = {
    "type": "function",
    "function": {
        "name": "submit_hypotheses",
        "description": "Submit ranked root-cause hypotheses for the incident.",
        "parameters": {
            "type": "object",
            "properties": {
                "hypotheses": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "description": {"type": "string"},
                            "confidence": {"type": "number"},
                            "suggested_actions": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "type": {"type": "string"},
                                        "description": {"type": "string"},
                                        "risk": {"type": "string"},
                                        "requires_approval": {"type": "boolean"},
                                        "params": {"type": "object"},
                                    },
                                },
                            },
                        },
                        "required": ["description", "confidence"],
                    },
                },
            },
            "required": ["hypotheses"],
        },
    },
}

_CRITIQUE_TOOL = {
    "type": "function",
    "function": {
        "name": "submit_critique",
        "description": "Critique whether timeline evidence supports the hypothesis.",
        "parameters": {
            "type": "object",
            "properties": {
                "supported": {"type": "boolean"},
                "reasoning": {"type": "string"},
                "confidence_adjustment": {
                    "type": "number",
                    "description": "Negative adjustment only, e.g. -0.3",
                },
            },
            "required": ["supported", "reasoning", "confidence_adjustment"],
        },
    },
}


@dataclass
class CritiqueResult:
    supported: bool
    reasoning: str
    confidence_adjustment: float


class HypothesisSynthesizer:
    def __init__(
        self,
        settings: Settings,
        usage_accumulator: LLMUsageAccumulator | None = None,
    ) -> None:
        self.settings = settings
        self._usage = usage_accumulator
        self._pool = LLMClientPool(settings, usage_accumulator=usage_accumulator)

    async def synthesize(self, incident: Incident) -> list[Hypothesis]:
        if self._pool.has_client() and incident.timeline:
            try:
                return await self._synthesize_llm(incident)
            except Exception as exc:
                logger.warning("LLM synthesis failed, using heuristic: %s", exc)
        return self._synthesize_heuristic(incident)

    async def critique(
        self, incident: Incident, hypothesis: Hypothesis
    ) -> CritiqueResult | None:
        if not self._pool.has_client():
            return None

        evidence = [
            e for e in incident.timeline if e.id in hypothesis.evidence_event_ids
        ]
        if not evidence:
            evidence = incident.timeline[:5]

        evidence_text = "\n".join(
            f"- [{e.at.isoformat()}] ({e.source}) {e.event}" for e in evidence
        )
        prompt = f"""Critique this top hypothesis against cited timeline evidence.

Hypothesis ({hypothesis.confidence:.0%} confidence): {hypothesis.description}

Evidence events:
{evidence_text}

Does the evidence actually support this conclusion? Is there a more likely alternative?
confidence_adjustment must be <= 0 (never inflate confidence).
"""

        try:
            response = await self._pool.chat_completion(
                model=self.settings.resolved_llm_model(),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                tools=[_CRITIQUE_TOOL],
                tool_choice={
                    "type": "function",
                    "function": {"name": "submit_critique"},
                },
            )
            message = response.choices[0].message
            tool_calls = getattr(message, "tool_calls", None) or []
            if not tool_calls:
                return None
            data = json.loads(tool_calls[0].function.arguments or "{}")
            adjustment = float(data.get("confidence_adjustment", 0.0))
            if adjustment > 0:
                adjustment = 0.0
            return CritiqueResult(
                supported=bool(data.get("supported", False)),
                reasoning=str(data.get("reasoning", "")),
                confidence_adjustment=adjustment,
            )
        except Exception as exc:
            logger.warning("Hypothesis critique failed, skipping: %s", exc)
            return None

    async def _synthesize_llm(self, incident: Incident) -> list[Hypothesis]:
        timeline_text = "\n".join(
            f"- [{e.at.isoformat()}] ({e.source}) {e.event}" for e in incident.timeline
        )
        prompt = f"""You are an SRE incident analyst. Given this incident and timeline, produce ranked hypotheses.

Incident: {incident.incident_id}
Service: {incident.service}
Namespace: {incident.namespace}
Severity: {incident.severity}
Trigger: {incident.trigger}

Timeline:
{timeline_text}

Rules:
- Only suggest rollback if timeline shows errors, crash loops, or clear metric degradation alongside a deploy.
- If signals are weak or cluster looks healthy, use investigate/escalate instead of rollback.
- Confidence must reflect evidence strength in the timeline.
- Call submit_hypotheses with your ranked hypotheses.
"""
        response = await self._pool.chat_completion(
            model=self.settings.resolved_llm_model(),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            tools=[_SUBMIT_HYPOTHESES_TOOL],
            tool_choice={
                "type": "function",
                "function": {"name": "submit_hypotheses"},
            },
        )
        message = response.choices[0].message
        tool_calls = getattr(message, "tool_calls", None) or []
        if not tool_calls:
            raise ValueError("LLM did not return submit_hypotheses tool call")
        data = json.loads(tool_calls[0].function.arguments or "{}")
        return self._parse_hypotheses(data, incident)

    def _synthesize_heuristic(self, incident: Incident) -> list[Hypothesis]:
        events = incident.timeline
        deploy_ev = [e for e in events if e.source == "deploy_correlator"]
        log_ev = [e for e in events if e.source == "logs_worker"]
        k8s_ev = [e for e in events if e.source == "k8s_worker"]
        metrics_ev = [e for e in events if e.source == "metrics_worker"]

        hypotheses: list[Hypothesis] = []

        has_deploy = len(deploy_ev) > 0
        has_runtime_errors = any(
            any(
                token in e.event.lower()
                for token in ("error", "exception", "crashloop", "failed", "oom")
            )
            for e in log_ev + k8s_ev
        )
        has_error_spike = any("error rate" in e.event.lower() for e in metrics_ev)

        if has_deploy and (has_runtime_errors or has_error_spike):
            revision = deploy_ev[0].metadata.get("revision", "unknown")
            prior = self._infer_prior_revision(revision)
            evidence_ids = [e.id for e in deploy_ev + log_ev + k8s_ev[:3]]
            hypotheses.append(
                Hypothesis(
                    id="H1",
                    description=(
                        f"Recent deploy (revision {revision}) correlates with "
                        f"runtime errors and/or elevated error rate"
                    ),
                    confidence=0.8,
                    evidence_event_ids=evidence_ids,
                    suggested_actions=[
                        SuggestedAction(
                            type="rollback",
                            description=f"Rollback {incident.service} to prior revision",
                            risk=ActionRisk.MEDIUM,
                            requires_approval=True,
                            params={
                                "service": incident.service,
                                "namespace": incident.namespace,
                                "current_revision": revision,
                                "target_revision": prior,
                            },
                        ),
                    ],
                )
            )

        if has_runtime_errors and not has_deploy:
            hypotheses.append(
                Hypothesis(
                    id="H1",
                    description="Runtime errors without a recent deploy — investigate dependency or config",
                    confidence=0.55,
                    evidence_event_ids=[e.id for e in log_ev + k8s_ev[:3]],
                    suggested_actions=[
                        SuggestedAction(
                            type="investigate",
                            description="Review logs and recent config/secret changes",
                            risk=ActionRisk.LOW,
                            requires_approval=False,
                        ),
                    ],
                )
            )

        if log_ev and len(hypotheses) < 2:
            hypotheses.append(
                Hypothesis(
                    id="H2",
                    description="Possible downstream dependency degradation",
                    confidence=0.25,
                    evidence_event_ids=[log_ev[0].id],
                    suggested_actions=[
                        SuggestedAction(
                            type="investigate",
                            description="Check external dependency dashboards and traces",
                            risk=ActionRisk.LOW,
                            requires_approval=False,
                        ),
                    ],
                )
            )

        if not hypotheses:
            hypotheses.append(
                Hypothesis(
                    id="H1",
                    description="Root cause unclear — insufficient signals from cluster",
                    confidence=0.1,
                    evidence_event_ids=[e.id for e in events[:5]],
                    suggested_actions=[
                        SuggestedAction(
                            type="escalate",
                            description="Escalate to human on-call with gathered timeline",
                            risk=ActionRisk.LOW,
                            requires_approval=False,
                        ),
                    ],
                )
            )

        return sorted(hypotheses, key=lambda h: h.confidence, reverse=True)

    def _infer_prior_revision(self, revision: str) -> str:
        try:
            n = int(revision)
            return str(max(1, n - 1))
        except ValueError:
            return "previous"

    def _parse_hypotheses(self, data: dict[str, Any], incident: Incident) -> list[Hypothesis]:
        raw = data.get("hypotheses", [])
        result: list[Hypothesis] = []

        for i, item in enumerate(raw):
            actions = []
            for a in item.get("suggested_actions", []):
                risk = ActionRisk(a.get("risk", "medium"))
                params = a.get("params", {})
                if "service" not in params:
                    params["service"] = incident.service
                if "namespace" not in params:
                    params["namespace"] = incident.namespace
                actions.append(
                    SuggestedAction(
                        type=a.get("type", "unknown"),
                        description=a.get("description", ""),
                        risk=risk,
                        requires_approval=a.get("requires_approval", True),
                        params=params,
                    )
                )
            ev_ids = [incident.timeline[j].id for j in range(min(3, len(incident.timeline)))]
            result.append(
                Hypothesis(
                    id=item.get("id", f"H{i+1}"),
                    description=item.get("description", ""),
                    confidence=float(item.get("confidence", 0.5)),
                    evidence_event_ids=ev_ids,
                    suggested_actions=actions,
                )
            )
        return sorted(result, key=lambda h: h.confidence, reverse=True)
