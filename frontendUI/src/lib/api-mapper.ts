import type {
  Hypothesis,
  Incident,
  PendingApproval,
  TimelineEvent,
  WorkerRun,
} from "./types";

/** Raw incident JSON from the FastAPI backend (`Incident.model_dump`). */
export type BackendIncident = {
  incident_id: string;
  status: string;
  opened_at: string;
  trigger: string;
  service: string;
  namespace: string;
  severity: string;
  environment?: string;
  summary?: string;
  timeline?: BackendTimelineEvent[];
  hypotheses?: BackendHypothesis[];
  worker_runs?: BackendWorkerRun[];
  approvals_pending?: BackendPendingApproval[];
  llm_usage?: {
    calls: number;
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
    estimated_cost_usd: number;
  };
};

type BackendTimelineEvent = {
  id: string;
  at: string;
  source: string;
  event: string;
  confidence?: string;
  metadata?: Record<string, unknown>;
};

type BackendSuggestedAction = {
  type: string;
  description: string;
  risk?: string;
  requires_approval?: boolean;
  params?: Record<string, unknown>;
};

type BackendHypothesis = {
  id: string;
  description: string;
  confidence: number;
  evidence_event_ids?: string[];
  suggested_actions?: BackendSuggestedAction[];
};

type BackendWorkerRun = {
  worker: string;
  status: string;
  iterations?: number;
  tools_called?: string[];
  summary?: string;
  error?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  steps?: Array<{
    iteration: number;
    thought?: string;
    action?: string | null;
    action_input?: Record<string, unknown>;
    observation?: string;
  }>;
};

type BackendPendingApproval = {
  id: string;
  status: string;
  action: BackendSuggestedAction;
  hypothesis_id?: string;
  requested_at?: string;
};

function mapTimeline(events: BackendTimelineEvent[] | undefined): TimelineEvent[] {
  const mapped = (events ?? []).map((e) => ({
    id: e.id,
    ts: e.at,
    source: e.source,
    message: e.event,
    detail:
      e.metadata && Object.keys(e.metadata).length > 0
        ? JSON.stringify(e.metadata, null, 2)
        : undefined,
  }));
  return mapped.sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime());
}

function formatSuggestedAction(action: BackendSuggestedAction): string {
  const risk = action.risk ? ` (${action.risk})` : "";
  return `${action.type}${risk}: ${action.description}`;
}

function mapHypotheses(
  hypotheses: BackendHypothesis[] | undefined,
  timeline: TimelineEvent[],
): Hypothesis[] {
  const eventById = new Map(timeline.map((e) => [e.id ?? "", e]));

  return (hypotheses ?? []).map((h) => ({
    id: h.id,
    description: h.description,
    confidence: h.confidence,
    suggested_actions: (h.suggested_actions ?? []).map(formatSuggestedAction),
    evidence: (h.evidence_event_ids ?? [])
      .map((id) => eventById.get(id)?.message)
      .filter((msg): msg is string => Boolean(msg)),
  }));
}

function mapWorkerStatus(status: string): WorkerRun["status"] {
  if (status === "complete") return "succeeded";
  if (status === "pending") return "queued";
  return status;
}

function mapWorkerRuns(
  runs: BackendWorkerRun[] | undefined,
  timeline: TimelineEvent[],
): WorkerRun[] {
  return (runs ?? []).map((run, idx) => {
    const started = run.started_at ?? undefined;
    const finished = run.finished_at ?? undefined;
    let duration_ms: number | undefined;
    if (started && finished) {
      duration_ms = new Date(finished).getTime() - new Date(started).getTime();
    }

    const findings = timeline.filter((e) => e.source === run.worker).length;

    return {
      id: `${run.worker}-${started ?? idx}`,
      worker: run.worker,
      status: mapWorkerStatus(run.status),
      ...(started ? { started_at: started } : {}),
      duration_ms,
      ...(findings > 0 ? { findings } : {}),
      ...(run.summary ? { summary: run.summary } : {}),
      ...(run.steps && run.steps.length > 0 ? { steps: run.steps } : {}),
    };
  });
}

function mapApprovals(approvals: BackendPendingApproval[] | undefined): PendingApproval[] {
  return (approvals ?? []).map((a) => ({
    id: a.id,
    status: a.status,
    action: {
      type: a.action.type,
      description: a.action.description,
      risk: a.action.risk ?? "medium",
    },
  }));
}

export function mapBackendIncident(raw: BackendIncident): Incident {
  const timeline = mapTimeline(raw.timeline);

  return {
    incident_id: raw.incident_id,
    status: raw.status as Incident["status"],
    opened_at: raw.opened_at,
    trigger: raw.trigger,
    service: raw.service,
    namespace: raw.namespace,
    severity: raw.severity as Incident["severity"],
    environment: raw.environment,
    summary: raw.summary ?? "",
    timeline,
    hypotheses: mapHypotheses(raw.hypotheses, timeline),
    worker_runs: mapWorkerRuns(raw.worker_runs, timeline),
    approvals_pending: mapApprovals(raw.approvals_pending),
    ...(raw.llm_usage && raw.llm_usage.calls > 0 ? { llm_usage: raw.llm_usage } : {}),
  };
}
