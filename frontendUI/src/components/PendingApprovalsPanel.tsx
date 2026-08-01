import { Link } from "@tanstack/react-router";
import { ArrowRight, ShieldAlert } from "lucide-react";
import { SeverityBadge, StatusBadge } from "./StatusBadge";
import { cn } from "@/lib/utils";
import type { Incident, PendingApproval } from "@/lib/types";

export interface PendingApprovalRow {
  incident: Incident;
  approval: PendingApproval;
}

export function collectPendingApprovals(incidents: Incident[]): PendingApprovalRow[] {
  const rows: PendingApprovalRow[] = [];
  for (const incident of incidents) {
    if (incident.status === "resolved" || incident.status === "escalated") {
      continue;
    }
    for (const approval of incident.approvals_pending) {
      rows.push({ incident, approval });
    }
  }
  const severityRank: Record<string, number> = { SEV1: 0, SEV2: 1, SEV3: 2, SEV4: 3 };
  return rows.sort((a, b) => {
    const sev =
      (severityRank[a.incident.severity] ?? 9) - (severityRank[b.incident.severity] ?? 9);
    if (sev !== 0) return sev;
    return b.incident.opened_at.localeCompare(a.incident.opened_at);
  });
}

const RISK_TONE: Record<string, string> = {
  high: "text-status-escalated border-status-escalated/40",
  medium: "text-status-mitigating border-status-mitigating/40",
  low: "text-status-resolved border-status-resolved/40",
};

export function PendingApprovalsPanel({
  rows,
  className,
}: {
  rows: PendingApprovalRow[];
  className?: string;
}) {
  const count = rows.length;

  return (
    <section
      className={cn(
        "rounded-lg border bg-surface",
        count > 0 ? "border-status-mitigating/35" : "border-border",
        className,
      )}
    >
      <div className="flex items-center justify-between gap-2 border-b border-border px-4 py-3">
        <h2 className="flex items-center gap-2 text-xs font-semibold tracking-wider uppercase">
          <ShieldAlert
            className={cn(
              "size-3.5",
              count > 0 ? "text-status-mitigating" : "text-muted-foreground",
            )}
          />
          Awaiting approval
          <span className="font-mono text-[11px] font-normal text-muted-foreground">
            ({count})
          </span>
        </h2>
      </div>

      {count === 0 ? (
        <p className="px-4 py-6 text-xs leading-relaxed text-muted-foreground">
          No destructive actions are waiting on a human. Rollback and scale approvals appear here
          as soon as the commander queues them.
        </p>
      ) : (
        <ul className="divide-y divide-border">
          {rows.map(({ incident, approval }) => (
            <li key={`${incident.incident_id}:${approval.id}`}>
              <Link
                to="/incidents/$id"
                params={{ id: incident.incident_id }}
                className="group flex items-start gap-3 px-4 py-3 transition-colors hover:bg-surface-raised"
              >
                <span
                  className={cn(
                    "mt-0.5 shrink-0 rounded border px-1.5 py-0.5 font-mono text-[10px] tracking-wider uppercase",
                    RISK_TONE[approval.action.risk] ?? RISK_TONE.medium,
                  )}
                >
                  {approval.action.type}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-xs font-semibold">
                      {incident.incident_id}
                    </span>
                    <SeverityBadge severity={incident.severity} />
                    <StatusBadge status={incident.status} />
                  </span>
                  <span className="mt-0.5 block font-mono text-[11px] text-muted-foreground">
                    deployment/{incident.service} · ns/{incident.namespace}
                  </span>
                  <span className="mt-1 block text-xs leading-relaxed text-foreground/90 line-clamp-2">
                    {approval.action.description}
                  </span>
                  <span className="mt-1 font-mono text-[10px] text-muted-foreground">
                    {approval.id} · risk {approval.action.risk}
                  </span>
                </span>
                <ArrowRight
                  className="mt-1 size-3.5 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5"
                />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
