import { useMemo, useState } from "react";
import { createFileRoute, useRouter } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { toast } from "sonner";
import { AppHeader } from "@/components/AppHeader";
import { IncidentList } from "@/components/IncidentList";
import {
  EMPTY_FILTERS,
  IncidentFilters,
  filterIncidents,
  isFiltering,
  type IncidentFilterState,
} from "@/components/IncidentFilters";
import { RefreshControl } from "@/components/RefreshControl";
import { PendingApprovalsPanel, collectPendingApprovals } from "@/components/PendingApprovalsPanel";
import { EscalationAlerts } from "@/components/EscalationAlerts";
import { useEscalationAlerts } from "@/hooks/use-escalation-alerts";
import { useAutoRefresh } from "@/hooks/use-auto-refresh";
import { OpenIncidentModal } from "@/components/OpenIncidentModal";
import { Button } from "@/components/ui/button";
import { createIncident, listIncidents } from "@/lib/api";
import { syncIncidentCaches } from "@/lib/incident-cache";
import type { CreateIncidentInput } from "@/lib/types";

export const Route = createFileRoute("/")({
  loader: async ({ context }) => {
    await context.queryClient.ensureQueryData({
      queryKey: ["incidents"],
      queryFn: listIncidents,
    });
  },
  head: () => ({
    meta: [
      { title: "Incident Commander — Kubernetes Incident Response" },
      {
        name: "description",
        content:
          "Multi-agent incident response for Kubernetes: correlated deploys, logs, metrics and cluster evidence with human-approved rollbacks.",
      },
      { property: "og:title", content: "Incident Commander — Kubernetes Incident Response" },
      {
        property: "og:description",
        content:
          "Triage K8s incidents with ranked AI hypotheses and approve rollbacks before kubectl touches production.",
      },
    ],
  }),
  component: Dashboard,
});

function Dashboard() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [filters, setFilters] = useState<IncidentFilterState>({ ...EMPTY_FILTERS });

  const {
    data: incidents = [],
    isPending,
    isFetching,
    error,
    refetch,
  } = useQuery({
    queryKey: ["incidents"],
    queryFn: listIncidents,
    refetchOnMount: "always",
    refetchOnWindowFocus: true,
  });

  const create = useMutation({
    mutationFn: (input: CreateIncidentInput) => createIncident(input),
    onSuccess: (incident) => {
      toast.success(`Incident ${incident.incident_id} opened`, {
        description: `Workers dispatched against deployment/${incident.service}.`,
      });
      setModalOpen(false);
      syncIncidentCaches(queryClient, incident);
      void router.navigate({
        to: "/incidents/$id",
        params: { id: incident.incident_id },
      });
    },
    onError: (err: Error) => {
      toast.error("Could not open incident", { description: err.message });
    },
  });

  const visible = useMemo(() => filterIncidents(incidents, filters), [incidents, filters]);
  const namespaces = useMemo(
    () => [...new Set(incidents.map((i) => i.namespace))].sort(),
    [incidents],
  );

  const active = incidents.filter(
    (i) => i.status !== "resolved" && i.status !== "escalated",
  ).length;
  const pendingRows = useMemo(() => collectPendingApprovals(incidents), [incidents]);
  const pendingApprovals = pendingRows.length;

  const alerts = useEscalationAlerts(incidents, !isPending);

  // Poll while incidents are active or approvals are waiting.
  const refresh = useAutoRefresh({
    intervalMs: 15_000,
    active: active > 0 || pendingApprovals > 0,
    onRefresh: () => refetch(),
  });

  return (
    <div className="min-h-screen">
      <AppHeader
        action={
          <Button size="sm" onClick={() => setModalOpen(true)}>
            <Plus className="size-3.5" />
            Open incident
          </Button>
        }
      />

      <main className="mx-auto max-w-7xl px-4 py-6 lg:px-6">
        <div className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
          <section className="overflow-hidden rounded-lg border border-border bg-surface">
            <div className="flex items-center justify-between border-b border-border px-4 py-3">
              <div>
                <h1 className="text-sm font-semibold">Incident board</h1>
                <span className="font-mono text-[11px] text-muted-foreground">
                  {incidents.length} total · {active} active
                </span>
              </div>
              <RefreshControl
                active={active > 0}
                enabled={refresh.enabled}
                paused={refresh.paused}
                secondsLeft={refresh.secondsLeft}
                lastRefreshedAt={refresh.lastRefreshedAt}
                isFetching={isFetching}
                onToggle={refresh.setEnabled}
                onRefreshNow={() => void refresh.refreshNow()}
              />
            </div>
            {!isPending && incidents.length > 0 ? (
              <IncidentFilters
                filters={filters}
                onChange={setFilters}
                namespaces={namespaces}
                resultCount={visible.length}
                totalCount={incidents.length}
              />
            ) : null}
            <IncidentList
              incidents={visible}
              isLoading={isPending}
              error={error as Error | null}
              onRetry={() => void refetch()}
              isRetrying={isFetching}
              isFiltered={isFiltering(filters)}
              onClearFilters={() => setFilters({ ...EMPTY_FILTERS })}
              onOpenIncidentModal={() => setModalOpen(true)}
            />
          </section>

          <aside className="space-y-4">
            <div className="rounded-lg border border-border bg-surface p-4">
              <p className="font-mono text-[11px] tracking-wider text-muted-foreground uppercase">
                Active incidents
              </p>
              <p className="mt-1 font-mono text-2xl font-semibold tabular-nums">{active}</p>
              <p className="mt-1 font-mono text-[11px] text-muted-foreground">
                {incidents.length} total on the board
              </p>
            </div>

            <PendingApprovalsPanel rows={pendingRows} />

            <EscalationAlerts alerts={alerts} />

            <div className="rounded-lg border border-border bg-surface p-4">
              <h2 className="text-xs font-semibold tracking-wider uppercase">How it works</h2>
              <ol className="mt-3 space-y-2.5 text-xs leading-relaxed text-muted-foreground">
                <li>
                  <span className="font-mono text-src-deploy">1 · workers</span> — deploy
                  correlator, logs, metrics and k8s agents gather evidence in parallel.
                </li>
                <li>
                  <span className="font-mono text-src-commander">2 · commander</span> — the model
                  ranks root-cause hypotheses by confidence.
                </li>
                <li>
                  <span className="font-mono text-status-mitigating">3 · you approve</span> — no
                  kubectl rollout undo runs until a human signs off.
                </li>
              </ol>
            </div>
          </aside>
        </div>
      </main>

      <OpenIncidentModal
        open={modalOpen}
        onOpenChange={setModalOpen}
        isSubmitting={create.isPending}
        onSubmit={(input) => create.mutate(input)}
      />
    </div>
  );
}
