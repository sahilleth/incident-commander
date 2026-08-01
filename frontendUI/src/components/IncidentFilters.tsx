import { Search, X } from "lucide-react";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import type { Incident, IncidentStatus, Severity } from "@/lib/types";

export interface IncidentFilterState {
  query: string;
  statuses: IncidentStatus[];
  severities: Severity[];
  namespace: string;
}

export const EMPTY_FILTERS: IncidentFilterState = {
  query: "",
  statuses: [],
  severities: [],
  namespace: "all",
};

const STATUSES: IncidentStatus[] = [
  "open",
  "investigating",
  "mitigating",
  "resolved",
  "escalated",
];
const SEVERITIES: Severity[] = ["SEV1", "SEV2", "SEV3", "SEV4"];

const STATUS_ACTIVE: Record<string, string> = {
  open: "border-status-open/50 bg-status-open/15 text-status-open",
  investigating: "border-status-investigating/50 bg-status-investigating/15 text-status-investigating",
  mitigating: "border-status-mitigating/50 bg-status-mitigating/15 text-status-mitigating",
  resolved: "border-status-resolved/50 bg-status-resolved/15 text-status-resolved",
  escalated: "border-status-escalated/50 bg-status-escalated/15 text-status-escalated",
};

export function filterIncidents(
  incidents: Incident[],
  filters: IncidentFilterState,
): Incident[] {
  const q = filters.query.trim().toLowerCase();
  return incidents.filter((i) => {
    if (filters.statuses.length && !filters.statuses.includes(i.status)) return false;
    if (filters.severities.length && !filters.severities.includes(i.severity)) return false;
    if (filters.namespace !== "all" && i.namespace !== filters.namespace) return false;
    if (!q) return true;
    return [i.incident_id, i.service, i.namespace, i.summary, i.trigger, i.environment ?? ""]
      .join(" ")
      .toLowerCase()
      .includes(q);
  });
}

export function isFiltering(filters: IncidentFilterState): boolean {
  return (
    filters.query.trim().length > 0 ||
    filters.statuses.length > 0 ||
    filters.severities.length > 0 ||
    filters.namespace !== "all"
  );
}

function Chip({
  label,
  active,
  activeClass,
  onClick,
}: {
  label: string;
  active: boolean;
  activeClass?: string | undefined;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        "rounded-full border px-2.5 py-0.5 font-mono text-[11px] tracking-wider uppercase transition-colors",
        active
          ? (activeClass ?? "border-primary/50 bg-primary/15 text-primary")
          : "border-border text-muted-foreground hover:border-foreground/30 hover:text-foreground",
      )}
    >
      {label}
    </button>
  );
}

export interface IncidentFiltersProps {
  filters: IncidentFilterState;
  onChange: (next: IncidentFilterState) => void;
  namespaces: string[];
  resultCount: number;
  totalCount: number;
}

export function IncidentFilters({
  filters,
  onChange,
  namespaces,
  resultCount,
  totalCount,
}: IncidentFiltersProps) {
  const toggle = <T extends string>(list: T[], value: T) =>
    list.includes(value) ? list.filter((v) => v !== value) : [...list, value];

  const dirty = isFiltering(filters);

  return (
    <div className="space-y-3 border-b border-border px-4 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-[200px] flex-1">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={filters.query}
            onChange={(e) => onChange({ ...filters, query: e.target.value })}
            placeholder="Filter by id, service, namespace, summary…"
            aria-label="Filter incidents"
            className="h-8 pl-8 font-mono text-xs"
          />
        </div>
        <select
          value={filters.namespace}
          onChange={(e) => onChange({ ...filters, namespace: e.target.value })}
          aria-label="Filter by namespace"
          className="h-8 rounded-md border border-border bg-background px-2 font-mono text-xs text-foreground outline-none focus-visible:border-primary/60"
        >
          <option value="all">all namespaces</option>
          {namespaces.map((ns) => (
            <option key={ns} value={ns}>
              ns/{ns}
            </option>
          ))}
        </select>
        {dirty ? (
          <button
            type="button"
            onClick={() => onChange({ ...EMPTY_FILTERS })}
            className="inline-flex items-center gap-1 font-mono text-[11px] text-muted-foreground hover:text-foreground"
          >
            <X className="size-3" />
            clear
          </button>
        ) : null}
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        {STATUSES.map((s) => (
          <Chip
            key={s}
            label={s}
            active={filters.statuses.includes(s)}
            activeClass={STATUS_ACTIVE[s]}
            onClick={() => onChange({ ...filters, statuses: toggle(filters.statuses, s) })}
          />
        ))}
        <span className="mx-1 h-4 w-px bg-border" aria-hidden />
        {SEVERITIES.map((s) => (
          <Chip
            key={s}
            label={s}
            active={filters.severities.includes(s)}
            onClick={() => onChange({ ...filters, severities: toggle(filters.severities, s) })}
          />
        ))}
        <span className="ml-auto font-mono text-[11px] text-muted-foreground tabular-nums">
          {resultCount}/{totalCount} shown
        </span>
      </div>
    </div>
  );
}
