# Quick Start - Separate Processes

## What I Built

Instead of one Python script that spawns subprocesses (which was hanging), I created **3 separate HTTP-based services**:

1. **GitLab MCP Server** (`gitlab_server_standalone.py`) - Port 8001
2. **LLM MCP Server** (`llm_server_standalone.py`) - Port 8002
3. **Client** (`standalone_client.py`) - Email monitor + orchestrator

## Why This is Better

✅ No subprocess spawning issues
✅ Ctrl+C works properly on each component
✅ Can restart individual services
✅ Production-ready architecture
✅ Better debugging with separate logs

## Setup (One Time)

```bash
# 1. Install dependencies (includes uvicorn and starlette for HTTP servers)
pip install -r requirements.txt

# 2. Configure (if not done already)
cp config.example.env .env
# Edit .env with your credentials
```

## Run It - Three Ways

### Way 1: Makefile - Background Processes (Easiest)

```bash
# Start all
make start-all

# Check status
make status

# View logs
make logs

# Stop all
make stop-all
```

### Way 2: tmux - Split Screen (Best for Development)

```bash
# Opens all 3 components in split terminal
make dev-all

# Detach: Ctrl+B then D
# Reattach: tmux attach -t gitlab-mr-summarizer
# Kill: Ctrl+C in each pane, then exit tmux
```

### Way 3: Manual - 3 Terminals (Maximum Control)

**Terminal 1:**
```bash
pyenv activate gitlab-reviewer
python -m src.servers.gitlab_server_standalone
```

**Terminal 2:**
```bash
pyenv activate gitlab-reviewer
python -m src.servers.llm_server_standalone
```

**Terminal 3 (wait 2-3 seconds for servers to start):**
```bash
pyenv activate gitlab-reviewer
python -m src.client.standalone_client
```

## What You'll See

**GitLab Server (Terminal 1):**
```
============================================================
GitLab MCP Server Starting...
URL: http://localhost:8001
SSE endpoint: http://localhost:8001/sse
============================================================
INFO:     Started server process
INFO:     Uvicorn running on http://0.0.0.0:8001
```

**LLM Server (Terminal 2):**
```
============================================================
Local LLM MCP Server Starting...
URL: http://localhost:8002
SSE endpoint: http://localhost:8002/sse
Model: codellama
============================================================
INFO:     Started server process
INFO:     Uvicorn running on http://0.0.0.0:8002
```

**Client (Terminal 3):**
```
============================================================
GitLab MR Summarizer Standalone Client Starting...
============================================================
Signal handlers registered
GitLab URL: https://gitlab.com
Email: your.email@gmail.com
Check Interval: 60s
GitLab MCP Server: http://localhost:8001
LLM MCP Server: http://localhost:8002
============================================================
✅ Client started successfully!
Monitoring for GitLab assignment notifications...
Press Ctrl+C to stop.
```

## Test It

1. **Get assigned to a GitLab MR** (or have someone assign you)
2. **Watch the client logs** - you'll see:
   ```
   Found GitLab assignment: [MR Title]
   MR URL: https://gitlab.com/...
   Processing MR...
   Step 1: Parsing MR URL...
   Step 2: Fetching MR metadata...
   Step 3: Fetching MR changes...
   Step 4: Generating summary with LLM...
   Step 5: Posting summary to MR...
   ✅ Successfully posted summary to MR
   ```

## Stop Everything

### If using Makefile:
```bash
make stop-all
```

### If using tmux:
- Press `Ctrl+C` in each pane
- Type `exit` to close tmux

### If manual terminals:
- Press `Ctrl+C` in each terminal (should exit cleanly now!)

## Files Created

```
src/servers/
  ├── gitlab_server_standalone.py  # HTTP/SSE GitLab MCP server
  └── llm_server_standalone.py     # HTTP/SSE LLM MCP server

src/client/
  └── standalone_client.py         # Client that connects via HTTP

Makefile                           # Easy commands
SEPARATE_PROCESSES_GUIDE.md        # Detailed guide
QUICK_START.md                     # This file
```

## Comparison with Old Approach

| | Old (`main.py`) | New (Separate) |
|---|---|---|
| **Start** | `python main.py` | `make start-all` |
| **Reliability** | Hangs on startup | ✅ Stable |
| **Ctrl+C** | Doesn't work | ✅ Works |
| **Debugging** | Hard | ✅ Easy |
| **Logs** | One file | Per component |
| **Production** | Not ready | ✅ Ready |

## Next Steps

1. **Try it**: Run `make dev-all` to see everything in action
2. **Test**: Get assigned to a GitLab MR
3. **Deploy**: Use `make start-all` to run in background

For more details, see [SEPARATE_PROCESSES_GUIDE.md](SEPARATE_PROCESSES_GUIDE.md)

