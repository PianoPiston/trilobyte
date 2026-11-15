.PHONY: setup dev api web test build docker smoke browser-qa
PYTHON ?= .venv/bin/python
PYTHON_BOOTSTRAP ?= python3

setup:
	$(PYTHON_BOOTSTRAP) -m venv .venv
	$(PYTHON) -m pip install -r requirements.txt
	cd web && npm install

dev:
	@echo "Run 'make api' and 'make web' in separate terminals."

api:
	$(PYTHON) -m uvicorn server.main:app --reload --host 127.0.0.1 --port 8100

web:
	cd web && npm run dev

test: build
	$(PYTHON) -m pytest

build:
	cd web && npm run build

smoke:
	$(PYTHON) scripts/smoke.py http://127.0.0.1:8100

browser-qa:
	DRIFTCI_URL=http://10.0.2.2:8100 bash scripts/browser-smoke-docker.sh

docker:
	docker compose up --build
