import { Link } from "@tanstack/react-router";
import { AlertTriangle, ChevronRight, Inbox, SearchX } from "lucide-react";
import { SeverityBadge, StatusBadge } from "./StatusBadge";
import { ErrorState } from "./ErrorState";
import { Skeleton } from "@/components/ui/skeleton";
import { relativeTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Incident } from "@/lib/types";

export interface IncidentListProps {
  incidents: Incident[];
  isLoading?: boolean;
  activeId?: string | undefined;
  onOpenIncidentModal?: (() => void) | undefined;
  /** Set when the last fetch failed, so the list shows a recoverable error state. */
  error?: Error | null | undefined;
  onRetry?: (() => void) | undefined;
  isRetrying?: boolean | undefined;
  /** True when filters are applied — changes the empty state copy. */
  isFiltered?: boolean | undefined;
  onClearFilters?: (() => void) | undefined;
}

export function IncidentList({
  incidents,
  isLoading,
  activeId,
  onOpenIncidentModal,
  error,
  onRetry,
  isRetrying,
  isFiltered,
  onClearFilters,
}: IncidentListProps) {
  if (isLoading) {
    return (
      <div className="divide-y divide-border">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="space-y-3 p-4">
            <div className="flex items-center gap-2">
              <Skeleton className="h-4 w-20" />
              <Skeleton className="h-4 w-14" />
              <Skeleton className="ml-auto h-4 w-24" />
            </div>
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-3 w-full" />
          </div>
        ))}
      </div>
    );
  }

  if (error && incidents.length === 0) {
    return (
      <ErrorState
        title="Incident board failed to load"
        message={error.message}
        {...(onRetry ? { onRetry } : {})}
        {...(isRetrying === undefined ? {} : { isRetrying })}
      />
    );
  }

  if (incidents.length === 0 && isFiltered) {
    return (
      <div className="flex flex-col items-center justify-center px-6 py-16 text-center">
        <div className="mb-4 flex size-11 items-center justify-center rounded-lg border border-border bg-surface-raised">
          <SearchX className="size-5 text-muted-foreground" />
        </div>
        <p className="text-sm font-medium">No incidents match these filters</p>
        <p className="mt-1 max-w-xs text-xs text-muted-foreground">
          Try widening the status or severity selection, or clear the search query.
        </p>
        {onClearFilters ? (
          <button
            onClick={onClearFilters}
            className="mt-4 font-mono text-xs text-primary underline-offset-4 hover:underline"
          >
            Clear filters
          </button>
        ) : null}
      </div>
    );
  }

  if (incidents.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center px-6 py-16 text-center">
        <div className="mb-4 flex size-11 items-center justify-center rounded-lg border border-border bg-surface-raised">
          <Inbox className="size-5 text-muted-foreground" />
        </div>
        <p className="text-sm font-medium">No incidents on the board</p>
        <p className="mt-1 max-w-xs text-xs text-muted-foreground">
          Every watched deployment is healthy. Open an incident manually to dispatch the worker
          fleet against a service.
        </p>
        {onOpenIncidentModal ? (
          <button
            onClick={onOpenIncidentModal}
            className="mt-4 font-mono text-xs text-primary underline-offset-4 hover:underline"
          >
            Open incident
          </button>
        ) : null}
      </div>
    );
  }


  return (
    <ul className="divide-y divide-border">
      {incidents.map((incident) => {
        const pending = incident.approvals_pending.length;
        return (
          <li key={incident.incident_id}>
            <Link
              to="/incidents/$id"
              params={{ id: incident.incident_id }}
              className={cn(
                "group block px-4 py-4 transition-colors hover:bg-surface-raised",
                activeId === incident.incident_id && "bg-surface-raised",
              )}
            >
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs text-muted-foreground">
                  {incident.incident_id}
                </span>
                <SeverityBadge severity={incident.severity} />
                <StatusBadge status={incident.status} />
                <span className="ml-auto font-mono text-[11px] text-muted-foreground">
                  {relativeTime(incident.opened_at)}
                </span>
                <ChevronRight className="size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
              </div>

              <div className="mt-2 flex flex-wrap items-baseline gap-x-2">
                <h3 className="font-mono text-sm font-semibold">{incident.service}</h3>
                <span className="font-mono text-xs text-muted-foreground">
                  ns/{incident.namespace}
                </span>
              </div>

              <p className="mt-1.5 line-clamp-2 text-xs leading-relaxed text-muted-foreground">
                {incident.summary}
              </p>

              {pending > 0 ? (
                <p className="mt-2 inline-flex items-center gap-1.5 rounded border border-status-mitigating/40 bg-status-mitigating/10 px-2 py-0.5 font-mono text-[11px] text-status-mitigating">
                  <AlertTriangle className="size-3" />
                  {pending} approval{pending > 1 ? "s" : ""} pending
                </p>
              ) : null}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
