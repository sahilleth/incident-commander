import { Link } from "@tanstack/react-router";
import { AlertOctagon, ArrowRight, BellRing, ShieldAlert } from "lucide-react";
import { cn } from "@/lib/utils";
import type { EscalationAlert } from "@/hooks/use-escalation-alerts";

const KIND = {
  escalated: {
    icon: AlertOctagon,
    label: "escalated",
    tone: "border-status-escalated/45 bg-status-escalated/10 text-status-escalated",
  },
  approval: {
    icon: ShieldAlert,
    label: "approval",
    tone: "border-status-mitigating/45 bg-status-mitigating/10 text-status-mitigating",
  },
  sev1: {
    icon: BellRing,
    label: "sev1",
    tone: "border-status-investigating/45 bg-status-investigating/10 text-status-investigating",
  },
} as const;

export function EscalationAlerts({ alerts }: { alerts: EscalationAlert[] }) {
  if (alerts.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-surface p-4">
        <h2 className="flex items-center gap-2 text-xs font-semibold tracking-wider uppercase">
          <BellRing className="size-3.5 text-muted-foreground" />
          Escalation alerts
        </h2>
        <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
          No escalations. Nothing is blocked on a human and no SEV1 is open — alerts appear here the
          moment an incident escalates or a destructive action needs sign-off.
        </p>
      </div>
    );
  }

  return (
    <section className="rounded-lg border border-status-escalated/30 bg-status-escalated/[0.04] p-4">
      <h2 className="flex items-center gap-2 text-xs font-semibold tracking-wider uppercase">
        <BellRing className="size-3.5 text-status-escalated" />
        Escalation alerts
        <span className="font-mono text-[11px] font-normal text-muted-foreground">
          ({alerts.length})
        </span>
      </h2>
      <ul className="mt-3 space-y-2">
        {alerts.map((alert) => {
          const meta = KIND[alert.kind];
          const Icon = meta.icon;
          return (
            <li key={alert.key}>
              <Link
                to="/incidents/$id"
                params={{ id: alert.incident_id }}
                className="group flex items-start gap-2.5 rounded-md border border-border bg-surface p-3 transition-colors hover:border-foreground/25"
              >
                <span
                  className={cn(
                    "mt-0.5 inline-flex items-center gap-1 rounded border px-1.5 py-0.5 font-mono text-[10px] tracking-wider uppercase",
                    meta.tone,
                  )}
                >
                  <Icon className="size-3" />
                  {meta.label}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block font-mono text-xs font-semibold">{alert.title}</span>
                  <span className="mt-0.5 block text-xs leading-relaxed text-muted-foreground">
                    {alert.detail}
                  </span>
                </span>
                <ArrowRight className="mt-1 size-3.5 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
              </Link>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
