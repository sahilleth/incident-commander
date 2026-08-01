# Contributing to Incident Commander

Thank you for your interest in contributing! This project welcomes bug reports, documentation improvements, eval fixtures, and code changes.

## Development setup

```bash
git clone https://github.com/sahilleth/incident-commander.git
cd incident-commander

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
# Optional: add GROQ_API_KEY for live LLM tests
```

### Local Kubernetes demo (optional)

```bash
./scripts/setup-k8s.sh
./scripts/setup-observability.sh
make scenario-bad-deploy
```

## Running checks

Before opening a pull request, run:

```bash
make check
```

This runs:

- Python compile check
- `pytest` (unit tests — no Groq API required)
- `incident-commander eval` (fixture scenarios)

Individual commands:

```bash
make test
make eval
incident-commander doctor   # requires cluster + observability for full check
```

## Pull request guidelines

1. **Scope** — One logical change per PR (feature, fix, or docs).
2. **Tests** — Add or update tests for behavior changes. Eval fixtures are welcome for new incident scenarios.
3. **No secrets** — Never commit `.env`, API keys, or `data/incidents.db`.
4. **Style** — Match existing code style; keep diffs focused.

## Adding eval scenarios

1. Create `src/incident_commander/eval/fixtures/your_scenario.json` with timeline + expected keywords.
2. Run `incident-commander eval` to verify scoring.
3. Optionally add `k8s/scenarios/` + `scripts/scenario-*.sh` for live reproduction.

Record a real incident as a fixture:

```bash
incident-commander record INC-...
```

## Reporting issues

Use GitHub Issues with:

- What you expected vs what happened
- `incident-commander doctor` output (redact secrets)
- Steps to reproduce

## Publishing to PyPI

Maintainers:

1. Create a [PyPI API token](https://pypi.org/manage/account/token/) with upload scope for `incident-commander`.
2. **One-time manual publish:** `PYPI_API_TOKEN=pypi-... make publish`
3. **GitHub Actions (recommended):** trusted publisher is configured for `publish.yml` — see [docs/PUBLISHING.md](docs/PUBLISHING.md).

```bash
make build    # wheel + sdist in dist/
```

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.
