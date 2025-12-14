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
LOGS_DIR := logs
PID_DIR := $(LOGS_DIR)

.PHONY: install backend-install frontend-install build backend-build frontend-build \
	run backend-run frontend-run clean stop backend-stop frontend-stop logs ensure-logs-dir

install: backend-install frontend-install

backend-install:
	cd $(BACKEND_DIR) && $(PYTHON) -m pip install -r requirements.txt

frontend-install:
	cd $(FRONTEND_DIR) && $(NPM) install

build: backend-build frontend-build

backend-build:
	@echo "No backend build step defined. Skipping."

frontend-build:
	cd $(FRONTEND_DIR) && $(NPM) install && $(NPM) run build

# Create logs directory
ensure-logs-dir:
	@mkdir -p $(LOGS_DIR)

# Run backend in background with logging
backend-run: ensure-logs-dir
	@echo "Starting backend..."
	@pkill -9 -f "uvicorn $(UVICORN_APP)" 2>/dev/null || true
	@sleep 0.5
	@cd $(BACKEND_DIR) && \
	( \
		if [ -f "$(VENV_ACTIVATE)" ]; then source "$(VENV_ACTIVATE)"; fi; \
		nohup $(PYTHON) -m $(UVICORN) $(UVICORN_APP) $(UVICORN_OPTS) \
			> ../$(LOGS_DIR)/backend.log 2>&1 & \
		echo $$! > ../$(PID_DIR)/backend.pid \
	)
	@sleep 0.5
	@echo "Backend started (PID: $$(cat $(PID_DIR)/backend.pid))"
	@echo "Logs: $(LOGS_DIR)/backend.log"

# Run frontend in background with logging
frontend-run: ensure-logs-dir
	@echo "Starting frontend..."
	@pkill -9 -f "vite" 2>/dev/null || true
	@sleep 0.5
	@cd $(FRONTEND_DIR) && \
	( \
		nohup $(NPM) run dev > ../$(LOGS_DIR)/frontend.log 2>&1 & \
		echo $$! > ../$(PID_DIR)/frontend.pid \
	)
	@sleep 0.5
	@echo "Frontend started (PID: $$(cat $(PID_DIR)/frontend.pid))"
	@echo "Logs: $(LOGS_DIR)/frontend.log"

# Run both backend and frontend in background
run: ensure-logs-dir
	@echo "Starting backend and frontend in background..."
	@$(MAKE) --no-print-directory backend-run
	@$(MAKE) --no-print-directory frontend-run
	@echo ""
	@echo "✓ Both services started in background"
	@echo "  Backend:  http://localhost:$(BACKEND_PORT)"
	@echo "  Frontend: http://localhost:$(FRONTEND_PORT)"
	@echo ""
	@echo "Use 'make logs' to tail logs or 'make stop' to stop services"

# Stop backend
backend-stop:
	@if [ -f $(PID_DIR)/backend.pid ]; then \
		PID=$$(cat $(PID_DIR)/backend.pid); \
		if kill -0 $$PID 2>/dev/null; then \
			echo "Stopping backend (PID: $$PID)..."; \
			kill $$PID 2>/dev/null || true; \
		else \
			echo "Backend not running (stale PID)"; \
		fi; \
		rm -f $(PID_DIR)/backend.pid; \
	else \
		echo "No backend PID file found"; \
		pkill -9 -f "uvicorn $(UVICORN_APP)" 2>/dev/null || true; \
	fi

# Stop frontend
frontend-stop:
	@if [ -f $(PID_DIR)/frontend.pid ]; then \
		PID=$$(cat $(PID_DIR)/frontend.pid); \
		if kill -0 $$PID 2>/dev/null; then \
			echo "Stopping frontend (PID: $$PID)..."; \
			kill $$PID 2>/dev/null || true; \
		else \
			echo "Frontend not running (stale PID)"; \
		fi; \
		rm -f $(PID_DIR)/frontend.pid; \
	else \
		echo "No frontend PID file found"; \
		pkill -9 -f "vite" 2>/dev/null || true; \
	fi

# Stop both services
stop: backend-stop frontend-stop
	@echo "All services stopped"

# Tail logs
logs:
	@echo "Tailing logs (Ctrl+C to stop)..."
	@tail -f $(LOGS_DIR)/backend.log $(LOGS_DIR)/frontend.log 2>/dev/null || echo "No logs found. Run 'make run' first."

clean:
	rm -rf $(FRONTEND_DIR)/node_modules $(FRONTEND_DIR)/dist
	rm -rf $(LOGS_DIR)


