export type IncidentStatus =
  | "open"
  | "investigating"
  | "mitigating"
  | "resolved"
  | "escalated";

export type Severity = "SEV1" | "SEV2" | "SEV3" | "SEV4";

export type TimelineSource =
  | "deploy_correlator"
  | "logs_worker"
  | "k8s_worker"
  | "metrics_worker"
  | "commander"
  | "human";

export interface TimelineEvent {
  id?: string;
  ts: string;
  source: TimelineSource | string;
  title?: string;
  message: string;
  detail?: string;
}

export interface Hypothesis {
  id: string;
  description: string;
  confidence: number; // 0-1
  suggested_actions: string[];
  evidence?: string[];
}

export interface WorkerRun {
  id: string;
  worker: string;
  status: "queued" | "running" | "succeeded" | "failed" | string;
  started_at?: string;
  duration_ms?: number;
  findings?: number;
}

export interface PendingApproval {
  id: string;
  status: string;
  action: {
    type: string;
    description: string;
    risk: "low" | "medium" | "high" | string;
  };
}

export interface Incident {
  incident_id: string;
  status: IncidentStatus;
  opened_at: string;
  trigger: string;
  service: string;
  namespace: string;
  severity: Severity;
  environment?: string;
  summary: string;
  timeline: TimelineEvent[];
  hypotheses: Hypothesis[];
  worker_runs: WorkerRun[];
  approvals_pending: PendingApproval[];
}

export interface CreateIncidentInput {
  service: string;
  namespace: string;
  trigger: string;
  severity: Severity;
  environment: string;
}
