"""Hypothesis synthesis — Groq (OpenAI-compatible) with heuristic fallback."""

import json
import logging
from typing import Any

from incident_commander.config import Settings
from incident_commander.llm.groq_client import GroqClientPool
from incident_commander.models.incident import (
    ActionRisk,
    Hypothesis,
    Incident,
    SuggestedAction,
)

logger = logging.getLogger(__name__)


class HypothesisSynthesizer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._pool = GroqClientPool(settings)

    async def synthesize(self, incident: Incident) -> list[Hypothesis]:
        if self._pool.has_client() and incident.timeline:
            try:
                return await self._synthesize_llm(incident)
            except Exception as exc:
                logger.warning("LLM synthesis failed, using heuristic: %s", exc)
        return self._synthesize_heuristic(incident)

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

Respond with JSON only:
{{
  "hypotheses": [
    {{
      "id": "H1",
      "description": "...",
      "confidence": 0.85,
      "suggested_actions": [
        {{
          "type": "rollback",
          "description": "...",
          "risk": "medium",
          "requires_approval": true,
          "params": {{"service": "{incident.service}", "namespace": "{incident.namespace}"}}
        }}
      ]
    }}
  ]
}}

Rules:
- Only suggest rollback if timeline shows errors, crash loops, or clear metric degradation alongside a deploy.
- If signals are weak or cluster looks healthy, use investigate/escalate instead of rollback.
- Confidence must reflect evidence strength in the timeline.
"""
        response = await self._pool.chat_completion(
            model=self.settings.resolved_llm_model(),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        data = json.loads(content)
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
