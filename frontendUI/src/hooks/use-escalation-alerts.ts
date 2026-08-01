import { useEffect, useMemo, useRef } from "react";
import { toast } from "sonner";
import type { Incident } from "@/lib/types";

export interface EscalationAlert {
  key: string;
  kind: "escalated" | "approval" | "sev1";
  incident_id: string;
  title: string;
  detail: string;
}

export function deriveAlerts(incidents: Incident[]): EscalationAlert[] {
  const alerts: EscalationAlert[] = [];
  for (const i of incidents) {
    if (i.status === "escalated") {
      alerts.push({
        key: `escalated:${i.incident_id}`,
        kind: "escalated",
        incident_id: i.incident_id,
        title: `${i.incident_id} escalated`,
        detail: `${i.service} · ns/${i.namespace} — automated mitigation failed, page the service owner.`,
      });
    }
    for (const a of i.approvals_pending) {
      alerts.push({
        key: `approval:${i.incident_id}:${a.id}`,
        kind: "approval",
        incident_id: i.incident_id,
        title: `${i.incident_id} awaiting approval`,
        detail: `${a.action.type} on ${i.service} (risk ${a.action.risk}) is blocked on a human.`,
      });
    }
    if (
      i.severity === "SEV1" &&
      i.status !== "resolved" &&
      i.status !== "escalated" &&
      i.approvals_pending.length === 0
    ) {
      alerts.push({
        key: `sev1:${i.incident_id}`,
        kind: "sev1",
        incident_id: i.incident_id,
        title: `${i.incident_id} is SEV1 and still ${i.status}`,
        detail: `${i.service} · ns/${i.namespace} — customer impact ongoing.`,
      });
    }
  }
  return alerts;
}

/**
 * Toasts (once) whenever a new escalation-worthy condition shows up between refreshes.
 */
export function useEscalationAlerts(
  incidents: Incident[],
  /** Set false while the first fetch is still pending so existing state isn't announced. */
  ready = true,
  enabled = true,
): EscalationAlert[] {
  const alerts = useMemo(() => deriveAlerts(incidents), [incidents]);
  const seen = useRef<Set<string> | null>(null);

  useEffect(() => {
    if (!enabled || !ready) return;
    const current = new Set(alerts.map((a) => a.key));
    if (seen.current === null) {
      // First render: adopt the baseline without shouting about existing state.
      seen.current = current;
      return;
    }
    for (const alert of alerts) {
      if (seen.current.has(alert.key)) continue;
      const notify = alert.kind === "approval" ? toast.warning : toast.error;
      notify(alert.title, { description: alert.detail });
    }
    seen.current = current;
  }, [alerts, enabled, ready]);

  return alerts;
}
