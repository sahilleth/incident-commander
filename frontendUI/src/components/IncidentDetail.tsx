import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { ArrowLeft, Download, Loader2, Search, ShieldAlert } from "lucide-react";
import { ErrorState } from "./ErrorState";
import { RefreshControl } from "./RefreshControl";
import { TimelineExportButton } from "./TimelineExportButton";
import { useAutoRefresh } from "@/hooks/use-auto-refresh";
import { ApprovalCard } from "./ApprovalCard";
import { AgentReasoningPanel } from "./AgentReasoningPanel";
import { HypothesisCard } from "./HypothesisCard";
import { Timeline } from "./Timeline";
import { SeverityBadge, StatusBadge, sourceMeta } from "./StatusBadge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";
import { approveAction, getIncident, getPostmortem, investigateIncident } from "@/lib/api";
import { syncIncidentCaches } from "@/lib/incident-cache";
import type { Incident } from "@/lib/types";
import { duration, fullTime, relativeTime } from "@/lib/format";
import { cn } from "@/lib/utils";

export interface IncidentDetailProps {
  incidentId: string;
}

export function IncidentDetail({ incidentId }: IncidentDetailProps) {
  const queryClient = useQueryClient();
  const [downloading, setDownloading] = useState(false);
  const [approvingId, setApprovingId] = useState<string | null>(null);

  const {
    data: incident,
    isPending,
    isError,
    error,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ["incident", incidentId],
    queryFn: () => getIncident(incidentId),
    refetchOnMount: "always",
  });

  const approve = useMutation({
    mutationFn: (approvalId: string) => approveAction(incidentId, approvalId),
    onMutate: async (approvalId) => {
      setApprovingId(approvalId);
      await queryClient.cancelQueries({ queryKey: ["incident", incidentId] });
      const previous = queryClient.getQueryData<Incident>(["incident", incidentId]);
      if (previous) {
        syncIncidentCaches(queryClient, {
          ...previous,
          status: "mitigating",
          approvals_pending: previous.approvals_pending.filter((a) => a.id !== approvalId),
        });
      }
      return { previous };
    },
    onSettled: () => {
      setApprovingId(null);
    },
    onSuccess: (updated) => {
      syncIncidentCaches(queryClient, updated);
      if (updated.status === "resolved") {
        toast.success("Action approved — incident resolved", {
          description: `Mitigation verified for ${updated.service}.`,
        });
      } else if (updated.status === "escalated") {
        toast.warning("Action ran but verification failed", {
          description: "The incident was escalated — check the timeline for verifier results.",
        });
      } else {
        toast.success("Action approved", {
          description: `${updated.status} — see timeline for execution details.`,
        });
      }
    },
    onError: (err: Error, _approvalId, context) => {
      if (context?.previous) {
        syncIncidentCaches(queryClient, context.previous);
      }
      toast.error("Approval failed", { description: err.message });
    },
  });

  const investigate = useMutation({
    mutationFn: () => investigateIncident(incidentId),
    onSuccess: (updated) => {
      syncIncidentCaches(queryClient, updated);
      toast.success("Re-investigation dispatched", { description: "Workers are running again." });
    },
    onError: (err: Error) => {
      toast.error("Investigation failed", { description: err.message });
    },
  });

  const live =
    incident?.status === "investigating" || incident?.status === "mitigating";
  const mutationBusy = approve.isPending || investigate.isPending;

  const refresh = useAutoRefresh({
    intervalMs: 15_000,
    active: live && !mutationBusy,
    onRefresh: () => refetch(),
  });

  const hypotheses = useMemo(
    () => [...(incident?.hypotheses ?? [])].sort((a, b) => b.confidence - a.confidence),
    [incident?.hypotheses],
  );

  async function downloadPostmortem() {
    setDownloading(true);
    try {
      const md = await getPostmortem(incidentId);
      const url = URL.createObjectURL(new Blob([md], { type: "text/markdown" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `${incidentId}-postmortem.md`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Postmortem downloaded");
    } catch (err) {
      toast.error("Could not download postmortem", { description: (err as Error).message });
    } finally {
      setDownloading(false);
    }
  }

  if (isPending) {
    return (
      <div className="space-y-6 p-6">
        <Skeleton className="h-5 w-40" />
        <Skeleton className="h-24 w-full" />
        <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
          <div className="space-y-3">
            <Skeleton className="h-28 w-full" />
            <Skeleton className="h-28 w-full" />
          </div>
          <Skeleton className="h-64 w-full" />
        </div>
      </div>
    );
  }

  if (isError || !incident) {
    return (
      <div className="mx-auto max-w-xl px-4 py-10">
        <ErrorState
          title={`Could not load ${incidentId}`}
          message={(error as Error | null)?.message ?? `No incident matched ${incidentId}.`}
          hint="The incident may have been purged, or the commander API is unreachable. Retry, or head back to the board."
          onRetry={() => void refetch()}
          isRetrying={isFetching}
        />
        <div className="flex justify-center">
          <Button size="sm" variant="ghost" asChild>
            <Link to="/">Back to board</Link>
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6 px-4 py-6 lg:px-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 font-mono text-xs text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="size-3.5" />
            incident board
          </Link>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <h1 className="font-mono text-xl font-semibold">{incident.incident_id}</h1>
            <SeverityBadge severity={incident.severity} />
            <StatusBadge status={incident.status} />
          </div>
          {incident.llm_usage ? (
            <p className="mt-1 font-mono text-[11px] text-muted-foreground">
              ${incident.llm_usage.estimated_cost_usd.toFixed(4)} · {incident.llm_usage.calls}{" "}
              LLM calls · {incident.llm_usage.total_tokens.toLocaleString()} tokens
            </p>
          ) : null}
        </div>

        <div className="flex flex-wrap gap-2">
          <RefreshControl
            active={live}
            enabled={refresh.enabled}
            paused={refresh.paused}
            secondsLeft={refresh.secondsLeft}
            lastRefreshedAt={refresh.lastRefreshedAt}
            isFetching={isFetching}
            onToggle={refresh.setEnabled}
            onRefreshNow={() => void refresh.refreshNow()}
          />
          <Button
            size="sm"
            variant="secondary"
            onClick={() => investigate.mutate()}
            disabled={investigate.isPending}
          >
            {investigate.isPending ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <Search className="size-3.5" />
            )}
            Re-investigate
          </Button>
          <Button size="sm" variant="secondary" onClick={downloadPostmortem} disabled={downloading}>
            {downloading ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <Download className="size-3.5" />
            )}
            Postmortem
          </Button>
        </div>
      </div>

      {/* Summary */}
      <section className="rounded-lg border border-border bg-surface p-4">
        <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[
            ["service", `deployment/${incident.service}`],
            ["namespace", incident.namespace],
            ["environment", incident.environment ?? "—"],
            ["opened", `${fullTime(incident.opened_at)} · ${relativeTime(incident.opened_at)}`],
          ].map(([label, value]) => (
            <div key={label}>
              <dt className="font-mono text-[11px] tracking-wider text-muted-foreground uppercase">
                {label}
              </dt>
              <dd className="mt-1 font-mono text-sm break-words">{value}</dd>
            </div>
          ))}
        </dl>
        <div className="mt-4 border-t border-border pt-4">
          <p className="font-mono text-[11px] tracking-wider text-muted-foreground uppercase">
            trigger
          </p>
          <p className="mt-1 font-mono text-xs text-foreground/90">{incident.trigger}</p>
          <p className="mt-3 text-sm leading-relaxed text-foreground/90">{incident.summary}</p>
        </div>
      </section>

      {/* Pending approvals */}
      <section>
        <h2 className="flex items-center gap-2 text-xs font-semibold tracking-wider uppercase">
          <ShieldAlert className="size-4 text-status-mitigating" />
          Pending approvals
          <span className="font-mono text-[11px] font-normal text-muted-foreground">
            ({incident.approvals_pending.length})
          </span>
        </h2>
        <div className="mt-3 space-y-3">
          {approve.isPending ? (
            <p className="flex items-center gap-2 rounded-lg border border-status-mitigating/40 bg-status-mitigating/10 px-4 py-3 text-xs text-status-mitigating">
              <Loader2 className="size-3.5 shrink-0 animate-spin" />
              Running kubectl action and verifying recovery — this can take up to a minute.
            </p>
          ) : null}
          {incident.approvals_pending.length === 0 ? (
            <p className="rounded-lg border border-dashed border-border px-4 py-6 text-center text-xs text-muted-foreground">
              Nothing waiting on a human. Destructive kubectl actions will appear here for approval
              before they run.
            </p>
          ) : (
            incident.approvals_pending.map((approval) => (
              <ApprovalCard
                key={approval.id}
                approval={approval}
                service={incident.service}
                namespace={incident.namespace}
                isApproving={approve.isPending && approvingId === approval.id}
                onApprove={(approvalId) => approve.mutate(approvalId)}
              />
            ))
          )}
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-[1.25fr_1fr]">
        <div className="space-y-6">
          <section>
            <h2 className="text-xs font-semibold tracking-wider uppercase">
              Ranked hypotheses
              <span className="ml-2 font-mono text-[11px] font-normal text-muted-foreground">
                ({hypotheses.length})
              </span>
            </h2>
            <div className="mt-3 space-y-3">
              {hypotheses.length === 0 ? (
                <p className="rounded-lg border border-dashed border-border px-4 py-6 text-center text-xs text-muted-foreground">
                  The model has not ranked any root causes yet — evidence is still being collected.
                </p>
              ) : (
                hypotheses.map((h, idx) => (
                  <HypothesisCard key={h.id} hypothesis={h} rank={idx + 1} />
                ))
              )}
            </div>
          </section>

          <section>
            <h2 className="text-xs font-semibold tracking-wider uppercase">Worker runs</h2>
            <div className="mt-3 overflow-x-auto rounded-lg border border-border bg-surface">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-border text-[11px] tracking-wider text-muted-foreground uppercase">
                  <tr>
                    <th className="px-3 py-2 font-medium">Worker</th>
                    <th className="px-3 py-2 font-medium">Status</th>
                    <th className="px-3 py-2 font-medium">Started</th>
                    <th className="px-3 py-2 font-medium">Duration</th>
                    <th className="px-3 py-2 font-medium">Findings</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border font-mono">
                  {incident.worker_runs.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-3 py-6 text-center text-muted-foreground">
                        No worker runs recorded.
                      </td>
                    </tr>
                  ) : (
                    incident.worker_runs.map((run) => {
                      const meta = sourceMeta(run.worker);
                      return (
                        <tr key={run.id} className="align-top">
                          <td className="px-3 py-2">
                            <span className="inline-flex items-center gap-2">
                              <span className={cn("size-1.5 rounded-full", meta.dot)} />
                              {run.worker}
                            </span>
                            <div className="mt-2 max-w-md">
                              <AgentReasoningPanel run={run} />
                            </div>
                          </td>
                          <td
                            className={cn(
                              "px-3 py-2",
                              run.status === "failed"
                                ? "text-status-escalated"
                                : run.status === "running"
                                  ? "text-status-investigating"
                                  : "text-status-resolved",
                            )}
                          >
                            {run.status}
                          </td>
                          <td className="px-3 py-2 text-muted-foreground">
                            {run.started_at ? relativeTime(run.started_at) : "—"}
                          </td>
                          <td className="px-3 py-2 text-muted-foreground tabular-nums">
                            {duration(run.duration_ms)}
                          </td>
                          <td className="px-3 py-2 text-muted-foreground tabular-nums">
                            {run.findings ?? 0}
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </section>
        </div>

        <section>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-xs font-semibold tracking-wider uppercase">
              Evidence timeline
              <span className="ml-2 font-mono text-[11px] font-normal text-muted-foreground">
                ({incident.timeline.length})
              </span>
            </h2>
            <TimelineExportButton incident={incident} />
          </div>
          <div className="mt-3 rounded-lg border border-border bg-surface p-4">
            <Timeline events={incident.timeline} />
          </div>
        </section>
      </div>
    </div>
  );
}
