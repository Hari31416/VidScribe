SHELL := /bin/bash

PYTHON ?= python3
UVICORN ?= uvicorn
UVICORN_APP ?= fastapi_app:app
UVICORN_OPTS ?= --host 0.0.0.0 --port 8000 --reload
BACKEND_DIR := backend
FRONTEND_DIR := frontend
NPM ?= npm
VENV_DIR ?= .venv
VENV_ACTIVATE := $(abspath $(VENV_DIR))/bin/activate
BACKEND_PORT ?= 8000
FRONTEND_PORT ?= 5173

.PHONY: install backend-install frontend-install build backend-build frontend-build \
	run backend-run frontend-run clean

install: backend-install frontend-install

backend-install:
	cd $(BACKEND_DIR) && $(PYTHON) -m pip install -r requirements.txt

frontend-install:
	cd $(FRONTEND_DIR) && $(NPM) install

build: backend-build frontend-build

backend-build:
	@echo "No backend build step defined. Skipping."

frontend-build:
	cd $(FRONTEND_DIR) && $(NPM) run build

backend-run:
	pkill -9 -f "uvicorn $(UVICORN_APP)" || true; \
	cd $(BACKEND_DIR) && \
	if [ -f "$(VENV_ACTIVATE)" ]; then source "$(VENV_ACTIVATE)"; fi; \
	$(PYTHON) -m $(UVICORN) $(UVICORN_APP) $(UVICORN_OPTS)

frontend-run:
	pkill -9 -f "npm run dev" || true; \
	cd $(FRONTEND_DIR) && $(NPM) run dev

run:
	@echo "Starting backend and frontend (Ctrl+C to stop both)..."
	@trap 'kill 0' INT TERM EXIT; \
		( \
		pkill -9 -f "uvicorn $(UVICORN_APP)" || true; \
		cd $(BACKEND_DIR); \
		if [ -f "$(VENV_ACTIVATE)" ]; then source "$(VENV_ACTIVATE)"; fi; \
		$(PYTHON) -m $(UVICORN) $(UVICORN_APP) $(UVICORN_OPTS) & \
		); \
		( \
		pkill -9 -f "npm run dev" || true; \
		cd $(FRONTEND_DIR); \
		$(NPM) run dev \
		); \
		wait

clean:
	rm -rf $(FRONTEND_DIR)/node_modules $(FRONTEND_DIR)/dist
