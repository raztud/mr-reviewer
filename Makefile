.PHONY: help install setup test clean start-gitlab-server start-llm-server start-client start-all stop-all restart-all status logs logs-gitlab logs-llm logs-client clean-all check-setup docker-build docker-up docker-down docker-logs docker-logs-client docker-logs-gitlab docker-logs-llm docker-status docker-restart docker-clean

# Variables
PYTHON := python
VENV := venv
PID_DIR := .pids

help:
	@echo "GitLab MR Summarizer - Makefile Commands"
	@echo ""
	@echo "Setup Commands:"
	@echo "  make install          - Install dependencies"
	@echo "  make setup            - Setup configuration"
	@echo "  make check-setup      - Check configuration"
	@echo ""
	@echo "Docker (Production - Recommended):"
	@echo "  make docker-build     - Build Docker images"
	@echo "  make docker-up        - Start all services in Docker"
	@echo "  make docker-down      - Stop Docker services"
	@echo "  make docker-logs      - View all Docker logs"
	@echo "  make docker-status    - Show Docker services status"
	@echo "  make docker-restart   - Restart Docker services"
	@echo ""
	@echo "Local Services (Development):"
	@echo "  make start-gitlab-server  - Start GitLab REST server"
	@echo "  make start-llm-server     - Start LLM REST server"
	@echo "  make start-client         - Start email monitor + client"
	@echo "  make start-all            - Start all services locally"
	@echo "  make stop-all             - Stop all local services"
	@echo "  make restart-all          - Restart all local services"
	@echo ""
	@echo "Logs:"
	@echo "  make logs             - View all logs"
	@echo "  make logs-client      - View client logs"
	@echo "  make docker-logs-client   - View Docker client logs"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean            - Clean temporary files"
	@echo "  make clean-all        - Clean logs and processed emails"
	@echo "  make docker-clean     - Clean Docker resources"

# Setup
install:
	@echo "Installing dependencies..."
	$(PYTHON) -m pip install -r requirements.txt

setup:
	@echo "Setting up configuration..."
	@if [ ! -f .env ]; then \
		cp config.example.env .env; \
		echo "Created .env file - please edit it with your credentials"; \
	else \
		echo ".env file already exists"; \
	fi
	@mkdir -p $(PID_DIR)
	@mkdir -p logs

check-setup:
	@echo "Testing setup..."
	$(PYTHON) check_setup.py

# Background processes
start-gitlab-server:
	@echo "Starting GitLab REST API server..."
	@mkdir -p $(PID_DIR) logs
	@nohup $(PYTHON) -m src.servers.gitlab_rest_server > logs/gitlab_server.log 2>&1 & echo $$! > $(PID_DIR)/gitlab_server.pid
	@echo "GitLab REST API server started (PID: $$(cat $(PID_DIR)/gitlab_server.pid))"

start-llm-server:
	@echo "Starting LLM REST API server..."
	@mkdir -p $(PID_DIR) logs
	@nohup $(PYTHON) -m src.servers.llm_rest_server > logs/llm_server.log 2>&1 & echo $$! > $(PID_DIR)/llm_server.pid
	@echo "LLM REST API server started (PID: $$(cat $(PID_DIR)/llm_server.pid))"

start-client:
	@echo "Starting email monitor + orchestrator..."
	@mkdir -p $(PID_DIR) logs
	@nohup $(PYTHON) -m src.client.standalone_client > logs/client.log 2>&1 & echo $$! > $(PID_DIR)/client.pid
	@echo "Client started (PID: $$(cat $(PID_DIR)/client.pid))"

start-all:
	@echo "Starting all components..."
	@$(MAKE) start-gitlab-server
	@sleep 2
	@$(MAKE) start-llm-server
	@sleep 2
	@$(MAKE) start-client
	@echo ""
	@echo "✅ All components started!"
	@echo ""
	@echo "View logs:"
	@echo "  make logs"
	@echo ""
	@echo "Stop all:"
	@echo "  make stop-all"

stop-all:
	@echo "Stopping all components..."
	@if [ -f $(PID_DIR)/client.pid ]; then \
		kill $$(cat $(PID_DIR)/client.pid) 2>/dev/null || true; \
		rm $(PID_DIR)/client.pid; \
		echo "Stopped client"; \
	fi
	@if [ -f $(PID_DIR)/llm_server.pid ]; then \
		kill $$(cat $(PID_DIR)/llm_server.pid) 2>/dev/null || true; \
		rm $(PID_DIR)/llm_server.pid; \
		echo "Stopped LLM server"; \
	fi
	@if [ -f $(PID_DIR)/gitlab_server.pid ]; then \
		kill $$(cat $(PID_DIR)/gitlab_server.pid) 2>/dev/null || true; \
		rm $(PID_DIR)/gitlab_server.pid; \
		echo "Stopped GitLab server"; \
	fi
	@echo "All components stopped"

restart-all:
	@$(MAKE) stop-all
	@sleep 1
	@$(MAKE) start-all

status:
	@echo "Component Status:"
	@echo ""
	@if [ -f $(PID_DIR)/gitlab_server.pid ]; then \
		if ps -p $$(cat $(PID_DIR)/gitlab_server.pid) > /dev/null 2>&1; then \
			echo "✅ GitLab Server: Running (PID: $$(cat $(PID_DIR)/gitlab_server.pid))"; \
		else \
			echo "❌ GitLab Server: Not running (stale PID)"; \
		fi \
	else \
		echo "❌ GitLab Server: Not running"; \
	fi
	@if [ -f $(PID_DIR)/llm_server.pid ]; then \
		if ps -p $$(cat $(PID_DIR)/llm_server.pid) > /dev/null 2>&1; then \
			echo "✅ LLM Server: Running (PID: $$(cat $(PID_DIR)/llm_server.pid))"; \
		else \
			echo "❌ LLM Server: Not running (stale PID)"; \
		fi \
	else \
		echo "❌ LLM Server: Not running"; \
	fi
	@if [ -f $(PID_DIR)/client.pid ]; then \
		if ps -p $$(cat $(PID_DIR)/client.pid) > /dev/null 2>&1; then \
			echo "✅ Client: Running (PID: $$(cat $(PID_DIR)/client.pid))"; \
		else \
			echo "❌ Client: Not running (stale PID)"; \
		fi \
	else \
		echo "❌ Client: Not running"; \
	fi

logs:
	@echo "Viewing logs (Ctrl+C to stop)..."
	@tail -f logs/*.log

logs-gitlab:
	@tail -f logs/gitlab_server.log

logs-llm:
	@tail -f logs/llm_server.log

logs-client:
	@tail -f logs/client.log

clean:
	@echo "Cleaning temporary files..."
	@rm -rf $(PID_DIR)
	@rm -rf __pycache__ src/__pycache__ src/*/__pycache__
	@rm -rf *.pyc src/*.pyc src/*/*.pyc
	@echo "Clean complete"

clean-all: clean
	@echo "Cleaning logs and processed emails..."
	@rm -rf logs
	@rm -f .processed_emails.json
	@echo "Full clean complete"

# =============================================================================
# Docker Commands
# =============================================================================

docker-build:
	@echo "Building Docker images..."
	docker-compose build
	@echo "✅ Docker images built"

docker-up:
	@echo "Starting services with Docker..."
	docker-compose up -d
	@echo "✅ All services started"
	@echo ""
	@echo "View logs with: make docker-logs"
	@echo "Check status with: make docker-status"

docker-down:
	@echo "Stopping Docker services..."
	docker-compose down
	@echo "✅ All services stopped"

docker-logs:
	@echo "Viewing all logs (Ctrl+C to stop)..."
	docker-compose logs -f

docker-logs-client:
	@echo "Client logs:"
	@docker-compose logs -f client

docker-logs-gitlab:
	@echo "GitLab server logs:"
	@docker-compose logs -f gitlab-server

docker-logs-llm:
	@echo "LLM server logs:"
	@docker-compose logs -f llm-server

docker-status:
	@echo "Docker Services Status:"
	@echo ""
	@docker-compose ps

docker-restart:
	@$(MAKE) docker-down
	@sleep 2
	@$(MAKE) docker-up

docker-clean:
	@echo "Cleaning Docker resources..."
	docker-compose down -v --rmi local
	@echo "✅ Docker resources cleaned"

