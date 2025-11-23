# Running with Separate Processes

This guide explains how to run the GitLab MR Summarizer with each component as a separate process (recommended for development and production).

## Architecture

Instead of one Python script that spawns subprocess MCP servers, we run three separate HTTP-based services:

```
┌──────────────────────┐
│  GitLab MCP Server   │  http://localhost:8001
│  (Port 8001)         │  Handles GitLab API calls
└──────────────────────┘

┌──────────────────────┐
│  LLM MCP Server      │  http://localhost:8002
│  (Port 8002)         │  Handles Ollama/LLM calls
└──────────────────────┘

┌──────────────────────┐
│  Client              │  Monitors email, coordinates workflow
│  (Email Monitor +    │  Connects to both MCP servers via HTTP
│   Orchestrator)      │
└──────────────────────┘
```

## Benefits

✅ **Independent restarts** - Restart just one component without affecting others
✅ **Better debugging** - See logs for each component separately
✅ **Production-ready** - Can deploy on different machines/containers
✅ **No subprocess issues** - No hanging on startup
✅ **Ctrl+C works!** - Clean shutdown for each component

## Quick Start

### Option 1: Using Makefile (Recommended)

Start all components with one command:

```bash
make start-all
```

Check status:

```bash
make status
```

View logs:

```bash
make logs          # All logs
make logs-gitlab   # Just GitLab server
make logs-llm      # Just LLM server
make logs-client   # Just client
```

Stop all:

```bash
make stop-all
```

### Option 2: Using tmux (Development)

Start all in split terminal windows:

```bash
make dev-all
```

This opens tmux with 3 panes:
- Top left: GitLab server
- Top right: LLM server
- Bottom: Client

Press `Ctrl+B` then `D` to detach. Reattach with:

```bash
tmux attach -t gitlab-mr-summarizer
```

### Option 3: Manual (3 Terminals)

**Terminal 1 - GitLab MCP Server:**
```bash
pyenv activate gitlab-reviewer
python -m src.servers.gitlab_server_standalone
```

**Terminal 2 - LLM MCP Server:**
```bash
pyenv activate gitlab-reviewer
python -m src.servers.llm_server_standalone
```

**Terminal 3 - Client:**
```bash
pyenv activate gitlab-reviewer
python -m src.client.standalone_client
```

## Configuration

Same `.env` file as before. Servers listen on:
- GitLab Server: `http://0.0.0.0:8001`
- LLM Server: `http://0.0.0.0:8002`

## Testing Individual Components

### Test GitLab Server

```bash
# Start server
python -m src.servers.gitlab_server_standalone

# In another terminal, test with curl:
curl -X POST http://localhost:8001/messages \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/list",
    "params": {},
    "id": 1
  }'
```

### Test LLM Server

```bash
# Start server
python -m src.servers.llm_server_standalone

# Test with curl:
curl -X POST http://localhost:8002/messages \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/list",
    "params": {},
    "id": 1
  }'
```

### Test Client

Make sure both servers are running first, then:

```bash
python -m src.client.standalone_client
```

## Deployment

### Docker Compose (Example)

```yaml
version: '3.8'

services:
  gitlab-server:
    build: .
    command: python -m src.servers.gitlab_server_standalone
    ports:
      - "8001:8001"
    env_file:
      - .env

  llm-server:
    build: .
    command: python -m src.servers.llm_server_standalone
    ports:
      - "8002:8002"
    env_file:
      - .env

  client:
    build: .
    command: python -m src.client.standalone_client
    depends_on:
      - gitlab-server
      - llm-server
    env_file:
      - .env
```

### systemd (Linux)

Create service files in `/etc/systemd/system/`:

**gitlab-mcp-server.service:**
```ini
[Unit]
Description=GitLab MCP Server
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/experiement-mcp
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/python -m src.servers.gitlab_server_standalone
Restart=always

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl enable gitlab-mcp-server
sudo systemctl start gitlab-mcp-server
```

## Troubleshooting

### Port Already in Use

```bash
# Find process using port
lsof -i :8001

# Kill it
kill -9 <PID>
```

### Server Won't Start

Check logs in `logs/` directory:
```bash
tail -f logs/gitlab_server.log
tail -f logs/llm_server.log
tail -f logs/client.log
```

### Client Can't Connect to Servers

Make sure servers are running:
```bash
curl http://localhost:8001/sse
curl http://localhost:8002/sse
```

Should return SSE connection (not 404).

## Comparison: Single Process vs. Separate Processes

| Feature | Single Process (`main.py`) | Separate Processes |
|---------|---------------------------|-------------------|
| **Startup** | `python main.py` | `make start-all` or 3 terminals |
| **Shutdown** | Ctrl+C (sometimes hangs) | Ctrl+C each or `make stop-all` |
| **Debugging** | One log file | Log per component |
| **Restart Component** | Restart everything | Restart just one |
| **Production** | Not ideal | Production-ready |
| **Complexity** | Simple | More setup |
| **Reliability** | Can hang on startup | More reliable |

## Recommended Usage

**Development**: Use `make dev-all` (tmux)
**Production**: Use `make start-all` or Docker Compose
**Quick Test**: Use single process `python main.py`

## Next Steps

1. Start with `make dev-all` to see all components running
2. Test by getting assigned to a GitLab MR
3. Watch logs to see the workflow
4. Deploy to production with systemd or Docker

---

For questions or issues, check the main [README.md](README.md).

