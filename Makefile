.PHONY: install test eval check doctor open setup-observability observability-forward scenario-bad-deploy stop-observability build publish frontend-install frontend-dev frontend-build

build:
	python3 -m pip install --upgrade build -q
	rm -rf dist/
	python3 -m build

publish:
	./scripts/publish-pypi.sh

install:
	python3 -m pip install -e ".[dev]"

test:
	pytest -q

eval:
	incident-commander eval

check:
	./scripts/check.sh

doctor:
	incident-commander doctor

setup-k8s:
	./scripts/setup-k8s.sh

setup-observability:
	./scripts/setup-observability.sh

observability-forward:
	./scripts/observability-forward.sh

scenario-bad-deploy:
	./scripts/scenario-bad-deploy.sh

scenario-%:
	./scripts/run-scenario.sh $*

stop-observability:
	./scripts/stop-observability.sh

frontend-install:
	cd frontendUI && bun install

frontend-dev:
	cd frontendUI && bun run dev

frontend-build:
	cd frontendUI && bun run build

frontend-e2e:
	./scripts/test-frontend-e2e.sh
