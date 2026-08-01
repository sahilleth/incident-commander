import { cn } from "@/lib/utils";
import type { IncidentStatus, Severity, TimelineSource } from "@/lib/types";

const STATUS_STYLES: Record<string, string> = {
  open: "text-status-open border-status-open/40 bg-status-open/10",
  investigating: "text-status-investigating border-status-investigating/40 bg-status-investigating/10",
  mitigating: "text-status-mitigating border-status-mitigating/40 bg-status-mitigating/10",
  resolved: "text-status-resolved border-status-resolved/40 bg-status-resolved/10",
  escalated: "text-status-escalated border-status-escalated/40 bg-status-escalated/10",
};

const STATUS_DOT: Record<string, string> = {
  open: "bg-status-open",
  investigating: "bg-status-investigating",
  mitigating: "bg-status-mitigating",
  resolved: "bg-status-resolved",
  escalated: "bg-status-escalated",
};

export function StatusBadge({
  status,
  className,
}: {
  status: IncidentStatus | string;
  className?: string;
}) {
  const live = status === "investigating" || status === "mitigating";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 font-mono text-[11px] font-medium uppercase tracking-wider",
        STATUS_STYLES[status] ?? STATUS_STYLES["open"],
        className,
      )}
    >
      <span
        className={cn(
          "size-1.5 rounded-full",
          STATUS_DOT[status] ?? STATUS_DOT["open"],
          live && "pulse-dot",
        )}
      />
      {status}
    </span>
  );
}

const SEV_STYLES: Record<string, string> = {
  SEV1: "text-sev1 border-sev1/45 bg-sev1/10",
  SEV2: "text-sev2 border-sev2/45 bg-sev2/10",
  SEV3: "text-sev3 border-sev3/45 bg-sev3/10",
  SEV4: "text-sev4 border-sev4/45 bg-sev4/10",
};

export function SeverityBadge({
  severity,
  className,
}: {
  severity: Severity | string;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded border px-1.5 py-0.5 font-mono text-[11px] font-semibold tracking-wider",
        SEV_STYLES[severity] ?? SEV_STYLES["SEV4"],
        className,
      )}
    >
      {severity}
    </span>
  );
}

export const SOURCE_META: Record<
  string,
  { label: string; dot: string; text: string; border: string; bg: string }
> = {
  deploy_correlator: {
    label: "deploy_correlator",
    dot: "bg-src-deploy",
    text: "text-src-deploy",
    border: "border-src-deploy/40",
    bg: "bg-src-deploy/10",
  },
  logs_worker: {
    label: "logs_worker",
    dot: "bg-src-logs",
    text: "text-src-logs",
    border: "border-src-logs/40",
    bg: "bg-src-logs/10",
  },
  k8s_worker: {
    label: "k8s_worker",
    dot: "bg-src-k8s",
    text: "text-src-k8s",
    border: "border-src-k8s/40",
    bg: "bg-src-k8s/10",
  },
  metrics_worker: {
    label: "metrics_worker",
    dot: "bg-src-metrics",
    text: "text-src-metrics",
    border: "border-src-metrics/40",
    bg: "bg-src-metrics/10",
  },
  commander: {
    label: "commander",
    dot: "bg-src-commander",
    text: "text-src-commander",
    border: "border-src-commander/40",
    bg: "bg-src-commander/10",
  },
  human: {
    label: "human",
    dot: "bg-src-human",
    text: "text-src-human",
    border: "border-src-human/40",
    bg: "bg-src-human/10",
  },
  runbook_executor: {
    label: "runbook",
    dot: "bg-status-mitigating",
    text: "text-status-mitigating",
    border: "border-status-mitigating/40",
    bg: "bg-status-mitigating/10",
  },
  verifier: {
    label: "verifier",
    dot: "bg-status-resolved",
    text: "text-status-resolved",
    border: "border-status-resolved/40",
    bg: "bg-status-resolved/10",
  },
};

export function sourceMeta(source: TimelineSource | string) {
  return SOURCE_META[source] ?? SOURCE_META["human"]!;
}
