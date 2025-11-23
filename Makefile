.PHONY: help install setup test clean start-gitlab-server start-llm-server start-client start-all stop-all restart-all status logs logs-gitlab logs-llm logs-client dev-gitlab dev-llm dev-client dev-all clean-all

# Variables
PYTHON := python
VENV := venv
PID_DIR := .pids

help:
	@echo "GitLab MR Summarizer - Makefile Commands"
	@echo ""
	@echo "Setup Commands:"
	@echo "  make install          - Install dependencies"
	@echo "  make setup           - Setup configuration"
	@echo "  make test-setup      - Test configuration"
	@echo ""
	@echo "Run Individual Components:"
	@echo "  make start-gitlab-server  - Start GitLab MCP server"
	@echo "  make start-llm-server     - Start LLM MCP server"
	@echo "  make start-client         - Start email monitor + orchestrator"
	@echo ""
	@echo "Run All (Recommended):"
	@echo "  make start-all       - Start all components in background"
	@echo "  make stop-all        - Stop all components"
	@echo "  make restart-all     - Restart all components"
	@echo "  make logs            - View logs"
	@echo ""
	@echo "Development:"
	@echo "  make dev-gitlab      - Run GitLab server in foreground"
	@echo "  make dev-llm         - Run LLM server in foreground"
	@echo "  make dev-client      - Run client in foreground"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean           - Clean temporary files"

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

test-setup:
	@echo "Testing setup..."
	$(PYTHON) test_setup.py

# Individual components (foreground for development)
dev-gitlab:
	@echo "Starting GitLab MCP server (foreground)..."
	$(PYTHON) -m src.servers.gitlab_server_standalone

dev-llm:
	@echo "Starting LLM MCP server (foreground)..."
	$(PYTHON) -m src.servers.llm_server_standalone

dev-client:
	@echo "Starting client (foreground)..."
	$(PYTHON) -m src.client.standalone_client

dev-all:
	@echo "Starting all components in tmux..."
	@if ! command -v tmux &> /dev/null; then \
		echo "Error: tmux not installed. Install with: brew install tmux"; \
		exit 1; \
	fi
	@tmux new-session -d -s gitlab-mr-summarizer
	@tmux split-window -h
	@tmux split-window -v
	@tmux select-pane -t 0
	@tmux send-keys "cd $(PWD) && $(PYTHON) -m src.servers.gitlab_server_standalone" C-m
	@tmux select-pane -t 1
	@tmux send-keys "cd $(PWD) && $(PYTHON) -m src.servers.llm_server_standalone" C-m
	@tmux select-pane -t 2
	@tmux send-keys "cd $(PWD) && sleep 3 && $(PYTHON) -m src.client.standalone_client" C-m
	@tmux attach-session -t gitlab-mr-summarizer
	@echo "Use Ctrl+B then D to detach from tmux"
	@echo "Use 'tmux attach -t gitlab-mr-summarizer' to reattach"

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

