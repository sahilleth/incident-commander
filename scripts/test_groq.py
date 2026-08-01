"""Quick Groq connectivity test — run: python scripts/test_groq.py"""

import asyncio

from incident_commander.config import get_settings
from incident_commander.llm.synthesizer import HypothesisSynthesizer
from incident_commander.models.incident import Incident, IncidentStatus, TimelineEvent
from datetime import datetime, timezone


async def main() -> None:
    settings = get_settings()
    if not settings.resolved_llm_api_key():
        print("FAIL: GROQ_API_KEY not set in .env")
        return

    incident = Incident(
        incident_id="TEST-001",
        status=IncidentStatus.INVESTIGATING,
        opened_at=datetime.now(timezone.utc),
        trigger="test",
        service="payment-api",
        namespace="default",
        timeline=[
            TimelineEvent(
                id="e1",
                at=datetime.now(timezone.utc),
                source="deploy_correlator",
                event="Deployment payment-api revision 42 rolled out",
                confidence="high",
                metadata={"revision": "42"},
            ),
            TimelineEvent(
                id="e2",
                at=datetime.now(timezone.utc),
                source="logs_worker",
                event="ERROR: NullPointerException in PaymentValidator",
                confidence="high",
            ),
        ],
    )

    synth = HypothesisSynthesizer(settings)
    hypotheses = await synth.synthesize(incident)

    print(f"Model: {settings.resolved_llm_model()}")
    print(f"Hypotheses: {len(hypotheses)}")
    for h in hypotheses:
        print(f"  {h.id} ({h.confidence:.0%}): {h.description}")
    print("OK: Groq LLM synthesis working")


if __name__ == "__main__":
    asyncio.run(main())
