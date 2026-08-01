# Incident Commander

[![CI](https://github.com/sahilleth/incident-commander/actions/workflows/ci.yml/badge.svg)](https://github.com/sahilleth/incident-commander/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/incident-commander.svg)](https://pypi.org/project/incident-commander/)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)

Multi-agent **Incident Commander** for production incidents. All integrations are **live** — kubectl, Loki, Prometheus, and Groq (optional). No mock mode.

## Agentic AI features

| Feature | Implementation |
|---------|----------------|
| **Worker ReAct loops** | Deterministic multi-step tools + optional Groq LLM ReAct per worker |
| **Post-action verification** | After rollback, polls pods/logs/metrics until healthy or escalate |
| **Eval / replay** | JSON fixtures, `incident-commander eval`, `incident-commander record` |

### ReAct workers

Each worker runs a **Reason → Act → Observe** loop (up to `MAX_WORKER_ITERATIONS`):

- **Deploy** — recent deploys → expanded lookback → rollout history → optional LLM
- **Logs** — error patterns → expanded window → optional LLM
- **K8s** — deployment pods → `app=` label fallback → warning events
- **Metrics** — Prometheus snapshot → retry → optional LLM

### Verification loop

After approved rollback:

1. Execute `kubectl rollout undo`
2. Poll every `VERIFY_INTERVAL_SECONDS` (default 15s)
3. Check pods healthy, errors quiet, error rate (if Prom available)
4. **Resolved** if checks pass, else **escalated**

### Eval / replay

```bash
incident-commander eval                    # built-in scenarios (packaged with pip install)
incident-commander record INC-...          # save incident as fixture
```

Built-in fixtures ship inside the Python package (`incident_commander/eval/fixtures/`).

## Prerequisites

- Python 3.11+
- Docker Desktop (running)
- `kubectl` (installed with Docker Desktop or separately)
- Optional: Prometheus, Loki, Groq API key

### One-time cluster setup (Docker + kind)

```bash
./scripts/setup-k8s.sh
```

This creates a **kind** cluster named `incident-commander` on Docker with **host ports wired** (`localhost:9090` → Prometheus, `localhost:3100` → Loki) and deploys a sample `payment-api` deployment. Config lives in `k8s/kind-config.yaml`.

If you already have a cluster without those ports:

```bash
KIND_RECREATE=1 ./scripts/setup-k8s.sh
```

### Observability (Prometheus + Loki)

```bash
./scripts/setup-observability.sh
```

Installs Prometheus, kube-state-metrics, Loki, and Promtail in the `monitoring` namespace. After setup, Prometheus and Loki are reachable on your Mac at `:9090` and `:3100` **without** `kubectl port-forward`.

Set in `.env`:

```env
LOG_BACKEND=loki
PROMETHEUS_URL=http://localhost:9090
LOKI_URL=http://localhost:3100
```

Optional fallback if host ports are missing: `./scripts/observability-forward.sh`

Or manually (new cluster with port wiring):

```bash
brew install kind          # if needed
kind create cluster --name incident-commander --config k8s/kind-config.yaml
kubectl apply -f k8s/sample-payment-api.yaml
```

## Health check (run before demos or commits)

```bash
make check
# or: ./scripts/check.sh
```

Runs: compile → pytest (10 tests) → eval fixtures (3 scenarios).

## Quick start

### Install from PyPI

```bash
pip install incident-commander

# Optional: configure cluster + LLM
cp .env.example .env   # from the GitHub repo, or set env vars directly

incident-commander doctor
incident-commander open payment-api --namespace default
```

PyPI: [pypi.org/project/incident-commander](https://pypi.org/project/incident-commander/)

### Clone for local development (kind demo + k8s scripts)

```bash
git clone https://github.com/sahilleth/incident-commander.git
cd incident-commander

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
# Optional: add GROQ_API_KEY — heuristic hypotheses work without it

./scripts/setup-k8s.sh
./scripts/setup-observability.sh
make scenario-bad-deploy

incident-commander open payment-api --namespace default
```

## CLI

| Command | Description |
|---------|-------------|
| `incident-commander open <deployment>` | Open + investigate (deployment name = K8s Deployment) |
| `incident-commander list` | Recent incidents |
| `incident-commander show INC-...` | Incident detail |
| `incident-commander approve INC-... APR-...` | Approve rollback (runs `kubectl rollout undo`) |
| `incident-commander serve` | API on `http://localhost:8080` |

### Options for `open`

```bash
incident-commander open payment-api \
  --namespace production \
  --trigger manual:health-check \
  --severity SEV1
```

## API

```bash
incident-commander serve

curl -X POST http://localhost:8080/incidents \
  -H 'Content-Type: application/json' \
  -d '{"service":"payment-api","namespace":"default","trigger":"manual"}'
```

## Architecture

```
Trigger (CLI / API) → Incident Commander (supervisor)
              ↓ parallel workers
    Deploy (kubectl rs) | Logs (Loki/kubectl) | K8s (pods/events) | Metrics (Prometheus)
              ↓
    Hypothesis synthesizer (Groq or heuristic)
              ↓
    Approval → Runbook executor (kubectl rollout undo) → Verifier
              ↓
    SQLite persistence
```

## Configuration

| Variable | Purpose |
|----------|---------|
| `GROQ_API_KEY` | Primary Groq LLM key (optional) |
| `GROQ_API_KEY_FALLBACK` | Second Groq key — used when primary is rate-limited |
| `GROQ_MODEL` | Default `llama-3.3-70b-versatile` |
| `KUBECONFIG` / `KUBE_CONTEXT` | Cluster access |
| `LOG_BACKEND` | `kubectl` or `loki` |
| `LOKI_URL` | Loki base URL |
| `PROMETHEUS_URL` | Prometheus base URL |
| `PROM_*_QUERY` | Custom PromQL templates |

**Service name** = Kubernetes **Deployment** name. Workers use the deployment's label selector for pods and replica sets.

## What each worker does (live)

| Worker | Data source |
|--------|-------------|
| Deploy correlator | `kubectl get rs` for deployment selector |
| Logs | Loki query_range or `kubectl logs` error lines |
| K8s | Pod status, restarts, warning events |
| Metrics | Prometheus instant queries |

## Groq setup

1. Get API key from [console.groq.com](https://console.groq.com)
2. Set in `.env`:

```env
GROQ_API_KEY=gsk_...
GROQ_API_KEY_FALLBACK=gsk_...   # optional second key
GROQ_MODEL=llama-3.3-70b-versatile
```

When the primary key hits rate limits or quota, requests automatically retry with `GROQ_API_KEY_FALLBACK`.

Without a key, the **heuristic synthesizer** still ranks hypotheses from timeline evidence.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Security reports: [SECURITY.md](SECURITY.md).

## Next steps

- [ ] Post-incident postmortem export
- [ ] Scale action implementation

## License

Apache License 2.0 — see [LICENSE](LICENSE).
