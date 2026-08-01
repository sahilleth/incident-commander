# Incident Commander

[![CI](https://github.com/sahilleth/incident-commander/actions/workflows/ci.yml/badge.svg)](https://github.com/sahilleth/incident-commander/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/incident-commander.svg)](https://pypi.org/project/incident-commander/)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)

**Open-source AI incident commander for Kubernetes.** When something breaks, Incident Commander opens an investigation, runs parallel agent workers against live cluster data, ranks root-cause hypotheses, and queues safe actions (like rollback) for human approval—then verifies recovery.

All integrations are **live**: `kubectl`, Prometheus, Loki, and Groq (optional). There is no mock mode.

```bash
pip install incident-commander
incident-commander doctor
incident-commander serve   # Web UI at http://localhost:8080/
incident-commander open payment-api --namespace default
```

**PyPI:** [pypi.org/project/incident-commander](https://pypi.org/project/incident-commander) · **Repo:** [github.com/sahilleth/incident-commander](https://github.com/sahilleth/incident-commander)

---

## Table of contents

- [Why Incident Commander](#why-incident-commander)
- [How it works](#how-it-works)
- [Quick start (pip)](#quick-start-pip)
- [Full local demo (kind + observability)](#full-local-demo-kind--observability)
- [End-to-end incident flow](#end-to-end-incident-flow)
- [CLI reference](#cli-reference)
- [API reference](#api-reference)
- [Configuration](#configuration)
- [Workers & data sources](#workers--data-sources)
- [Eval & replay](#eval--replay)
- [Development](#development)
- [Contributing & security](#contributing--security)
- [Roadmap](#roadmap)
- [License](#license)

---

## Why Incident Commander

| Tool | Gap |
|------|-----|
| **kubectl / k9s** | Manual, no correlation across deploys, logs, metrics |
| **Dashboards** | Show data; don't build a ranked incident narrative |
| **Enterprise AIOps** | Often closed-source, heavy, or cloud-only |

Incident Commander fills the gap for homelab, small teams, and anyone who wants **agentic incident response** on a real cluster—with **human approval** before destructive actions.

**What you get:**

- **Multi-agent ReAct workers** — deploy, logs, K8s state, and metrics in parallel
- **Hypothesis synthesis** — Groq LLM or deterministic heuristics when no API key
- **Human-in-the-loop rollback** — `kubectl rollout undo` only after approval
- **Post-mitigation verifier** — polls until healthy or escalates
- **Eval harness** — score hypothesis quality on JSON fixtures

---

## How it works

```mermaid
flowchart TD
    T[Trigger: CLI or API] --> S[Supervisor]
    S --> W1[Deploy correlator]
    S --> W2[Logs worker]
    S --> W3[K8s worker]
    S --> W4[Metrics worker]
    W1 --> TL[Incident timeline]
    W2 --> TL
    W3 --> TL
    W4 --> TL
    TL --> H[Hypothesis synthesizer]
    H --> A{Rollback suggested?}
    A -->|Yes| P[Pending approval]
    A -->|No| I[Investigating / resolved]
    P -->|Human approves| R[Runbook: rollout undo]
    R --> V[Verifier loop]
    V -->|Healthy| RES[Resolved]
    V -->|Still broken| ESC[Escalated]
    TL --> DB[(SQLite)]
```

1. **Trigger** — You open an incident for a Kubernetes **Deployment** name.
2. **Workers** — Four agents gather evidence via ReAct loops (deterministic tools + optional LLM).
3. **Synthesize** — Timeline is turned into ranked hypotheses with suggested actions.
4. **Approve** — High-risk actions (rollback) require explicit approval.
5. **Execute & verify** — Rollback runs, then pods/logs/metrics are polled until stable.

**Service name = Deployment name.** Workers resolve pods and ReplicaSets from the deployment's label selector.

---

## Quick start (pip)

For any cluster you already have access to via `kubectl`:

```bash
pip install incident-commander

# Configure (copy from repo or set env vars)
export KUBE_CONTEXT=your-context          # optional
export PROMETHEUS_URL=http://localhost:9090   # if Prometheus reachable
export LOKI_URL=http://localhost:3100           # if using Loki
export LOG_BACKEND=loki                         # or kubectl
export GROQ_API_KEY=gsk_...                     # optional

incident-commander doctor
incident-commander open my-deployment --namespace default --trigger manual:health-check
incident-commander list
incident-commander show INC-20260801-XXXXXX
```

Without `GROQ_API_KEY`, hypotheses still work via **heuristic ranking** from timeline evidence.

---

## Full local demo (kind + observability)

Run the entire stack on your laptop with Docker, kind, Prometheus, and Loki—no port-forward required (host ports are wired in `k8s/kind-config.yaml`).

### Prerequisites

- Python 3.11+
- Docker Desktop (running)
- `kubectl`
- `kind` (`brew install kind`)

### 1. Clone and install

```bash
git clone https://github.com/sahilleth/incident-commander.git
cd incident-commander

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
# Optional: add GROQ_API_KEY and GROQ_API_KEY_FALLBACK
```

### 2. Create cluster + sample app

```bash
./scripts/setup-k8s.sh
```

Creates kind cluster `incident-commander`, wires **localhost:9090** (Prometheus) and **localhost:3100** (Loki), and deploys sample `payment-api`.

If an old cluster lacks host ports:

```bash
KIND_RECREATE=1 ./scripts/setup-k8s.sh
```

### 3. Install observability stack

```bash
./scripts/setup-observability.sh
```

Deploys Prometheus, kube-state-metrics, Loki, and Promtail into namespace `monitoring`.

Ensure `.env` includes:

```env
LOG_BACKEND=loki
PROMETHEUS_URL=http://localhost:9090
LOKI_URL=http://localhost:3100
KUBE_CONTEXT=kind-incident-commander
```

### 4. Verify environment

```bash
incident-commander doctor
```

Expect: `kubectl`, `prometheus`, `loki`, and `groq` (if configured) all **ok**.

### 5. Run a scripted bad-deploy scenario

```bash
make scenario-bad-deploy
```

This applies a broken rollout (crashloop + error logs), runs a full investigation, prints hypotheses, and restores the healthy deployment.

---

## End-to-end incident flow

### 1. Open and investigate

```bash
incident-commander open payment-api \
  --namespace default \
  --trigger pagerduty:high-error-rate \
  --severity SEV1
```

Workers run in parallel. Output includes timeline, worker summaries, ranked hypotheses, and any **pending approvals**.

### 2. Review

```bash
incident-commander show INC-20260801-XXXXXX
```

### 3. Approve rollback (if suggested)

```bash
incident-commander approve INC-20260801-XXXXXX APR-xxxxxxxx
```

Runs `kubectl rollout undo`, then the **verifier** polls every `VERIFY_INTERVAL_SECONDS` (default 15s) until:

- Pods are healthy
- Error logs quiet down
- Error rate acceptable (if Prometheus is available)

Outcome: **resolved** or **escalated**.

### Example timeline (bad deploy)

| Source | Signal |
|--------|--------|
| `deploy_correlator` | New ReplicaSet revision 4 |
| `logs_worker` | `NullPointerException in PaymentValidator` (Loki) |
| `k8s_worker` | Pod crashloop, 2 restarts |
| `metrics_worker` | Elevated restart rate (Prometheus) |

**Hypothesis (85%):** Recent deploy introduced regression → **rollback** queued for approval.

---

## CLI reference

| Command | Description |
|---------|-------------|
| `incident-commander open <deployment>` | Open incident and run all workers |
| `incident-commander list` | List recent incidents |
| `incident-commander show <INC-ID>` | Full incident detail |
| `incident-commander approve <INC-ID> <APR-ID>` | Approve action (e.g. rollback) |
| `incident-commander doctor` | Check kubectl, Prom, Loki, Groq |
| `incident-commander eval` | Run built-in eval scenarios |
| `incident-commander record <INC-ID>` | Export incident as eval fixture |
| `incident-commander export <INC-ID>` | Postmortem Markdown (`-o` file) |
| `incident-commander serve` | REST API + Web UI at `http://localhost:8080/` |

### `open` options

```bash
incident-commander open payment-api \
  --namespace production \
  --trigger manual:health-check \
  --severity SEV1
```

| Option | Default | Description |
|--------|---------|-------------|
| `--namespace` | `default` | Kubernetes namespace |
| `--trigger` | `manual` | Source label (PagerDuty, alert name, etc.) |
| `--severity` | `SEV2` | SEV1–SEV4 style label |

---

## API reference

```bash
incident-commander serve
# API docs: http://localhost:8080/docs
```

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` , `/ui` | Web UI (timeline + approve) |
| `GET` | `/health` | Health check |
| `POST` | `/incidents` | Open + investigate |
| `GET` | `/incidents` | List recent |
| `GET` | `/incidents/{id}` | Get incident |
| `GET` | `/incidents/{id}/postmortem.md` | Postmortem Markdown |
| `POST` | `/incidents/{id}/investigate` | Re-run workers |
| `POST` | `/incidents/{id}/approve` | Approve pending action |
| `POST` | `/webhooks/alertmanager` | Alertmanager → auto-open incidents |

**Open incident:**

```bash
curl -s -X POST http://localhost:8080/incidents \
  -H 'Content-Type: application/json' \
  -d '{
    "service": "payment-api",
    "namespace": "default",
    "trigger": "manual",
    "severity": "SEV2"
  }'
```

**Approve rollback:**

```bash
curl -s -X POST http://localhost:8080/incidents/INC-.../approve \
  -H 'Content-Type: application/json' \
  -d '{"approval_id": "APR-..."}'
```

**Alertmanager webhook** (configure in Prometheus Alertmanager):

```yaml
receivers:
  - name: incident-commander
    webhook_configs:
      - url: http://incident-commander:8080/webhooks/alertmanager
        send_resolved: false
```

Labels `deployment`, `service`, or `app` on alerts map to the incident service name.

> The API has no authentication in v0.2.0. Do not expose it on untrusted networks.

---

## Configuration

Copy `.env.example` to `.env` or set environment variables.

### LLM (Groq or Ollama)

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `groq` | `groq`, `ollama`, or `openai` |
| `GROQ_API_KEY` | — | Primary Groq API key ([console.groq.com](https://console.groq.com)) |
| `GROQ_API_KEY_FALLBACK` | — | Second key; used when primary is rate-limited |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model name |
| `OLLAMA_MODEL` | `llama3.2` | Ollama model when using local LLM |
| `LLM_BASE_URL` | Groq URL | OpenAI-compatible base URL |

**Ollama (no cloud API key):**

```bash
ollama pull llama3.2
export LLM_PROVIDER=ollama
export LLM_BASE_URL=http://localhost:11434
incident-commander doctor
```

### Kubernetes

| Variable | Default | Description |
|----------|---------|-------------|
| `KUBECONFIG` | — | Path to kubeconfig |
| `KUBE_CONTEXT` | — | Context name (e.g. `kind-incident-commander`) |

### Logs

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_BACKEND` | `kubectl` | `loki` or `kubectl` (pod log tail) |
| `LOKI_URL` | `http://localhost:3100` | Loki base URL |

### Metrics

| Variable | Default | Description |
|----------|---------|-------------|
| `PROMETHEUS_URL` | `http://localhost:9090` | Prometheus base URL |
| `PROM_ERROR_RATE_QUERY` | kube-state-metrics restart rate | PromQL; use `{service}` and `{namespace}` |
| `PROM_P99_LATENCY_QUERY` | `vector(0)` | Override for app latency metrics |
| `PROM_REQUEST_RATE_QUERY` | pod count query | Override for RPS-style metrics |

Default Prom queries use **kube-state-metrics**. If your app exports `http_requests_total`, override the `PROM_*_QUERY` templates in `.env`.

### Orchestrator

| Variable | Default | Description |
|----------|---------|-------------|
| `INCIDENT_DB_PATH` | `./data/incidents.db` | SQLite database |
| `MAX_WORKER_ITERATIONS` | `5` | ReAct loop limit per worker |
| `WORKER_TIMEOUT_SECONDS` | `120` | Worker timeout |
| `KUBECTL_TIMEOUT_SECONDS` | `30` | kubectl command timeout |
| `DEPLOY_LOOKBACK_MINUTES` | `60` | How far back to search for deploys |
| `VERIFY_MAX_ATTEMPTS` | `5` | Verifier poll attempts after rollback |
| `VERIFY_INTERVAL_SECONDS` | `15` | Seconds between verifier polls |
| `VERIFY_MAX_ERROR_COUNT` | `10` | Max error log lines before fail |

---

## Workers & data sources

Each worker runs a **Reason → Act → Observe** loop (deterministic steps first, optional Groq ReAct if configured).

| Worker | What it does | Data source |
|--------|----------------|-------------|
| **deploy_correlator** | Recent ReplicaSets, rollout history | `kubectl get rs`, rollout history |
| **logs_worker** | Top error patterns in time window | Loki `query_range` or `kubectl logs` |
| **k8s_worker** | Pod health, restarts, warning events | Pod status, events API |
| **metrics_worker** | Error rate, RPS, latency snapshot | Prometheus instant queries |

Workers run **in parallel**. Results merge into a single timeline before hypothesis synthesis.

---

## Eval & replay

Built-in scenarios ship with the package (no extra download):

```bash
incident-commander eval
```

| Scenario | What it tests |
|----------|----------------|
| `bad_deploy` | Deploy + NPE + crashloop → rollback suggestion |
| `crashloop_no_deploy` | Errors without recent deploy |
| `healthy_cluster` | Weak signals → no false rollback |

Record a real incident as a fixture:

```bash
incident-commander record INC-20260801-XXXXXX
```

Fixture source files: `src/incident_commander/eval/fixtures/`.

---

## Development

```bash
make install          # editable install with dev deps
make test             # pytest
make eval             # eval scenarios
make check            # compile + test + eval (CI runs this)
make scenario-bad-deploy   # live kind scenario
make build            # wheel for PyPI
```

### Project layout

```
src/incident_commander/
  agents/          # ReAct loop engine
  workers/         # Deploy, logs, k8s, metrics
  orchestrator/    # Commander, runbook, verifier
  llm/             # Groq client + synthesizer
  tools/           # kubectl, Prometheus, Loki clients
  eval/            # Replay runner + fixtures
  api/             # FastAPI app
k8s/               # kind config, monitoring, sample apps, scenarios
scripts/           # setup-k8s, observability, scenarios
tests/
```

### Makefile targets (clone only)

| Target | Description |
|--------|-------------|
| `make setup-k8s` | Create kind cluster + payment-api |
| `make setup-observability` | Prometheus + Loki on kind |
| `make scenario-bad-deploy` | Live bad-deploy demo |
| `make scenario-imagepull` | ImagePullBackOff scenario |
| `make scenario-oom` | OOMKilled scenario |
| `make scenario-crashloop-runtime` | Runtime crashloop (dependency errors) |
| `make observability-forward` | Fallback port-forward if host ports missing |

---

## Contributing & security

- [CONTRIBUTING.md](CONTRIBUTING.md) — dev setup, PRs, eval fixtures
- [SECURITY.md](SECURITY.md) — report vulnerabilities privately
- [docs/PUBLISHING.md](docs/PUBLISHING.md) — PyPI release process

---

## Roadmap

- [x] Ollama / local LLM
- [x] Alertmanager webhook trigger
- [x] Web UI (timeline + approve)
- [x] Postmortem Markdown export
- [x] Live scenarios (imagepull, OOM, crashloop-runtime)
- [ ] Postmortem PDF export
- [ ] Helm chart for in-cluster deployment
- [ ] Additional runbooks (scale, restart)

---

## License

Apache License 2.0 — see [LICENSE](LICENSE).

Copyright 2026 Incident Commander Contributors
