# Project Overview - GitLab MR Summarizer

## What You Have Now

A complete, working system that automatically:
1. Monitors your Gmail for GitLab assignment notifications
2. Fetches merge request details via MCP servers
3. Generates AI summaries using your local Ollama LLM
4. Posts summaries as comments on GitLab MRs

## Quick Start

```bash
# 1. Install dependencies
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Setup Ollama
ollama serve &
ollama pull codellama

# 3. Configure
cp config.example.env .env
# Edit .env with your credentials

# 4. Run
python main.py
```

See [SETUP_GUIDE.md](SETUP_GUIDE.md) for detailed setup instructions.

## Project Structure

```
experiement-mcp/
├── main.py                          # Main service entry point
├── requirements.txt                 # Python dependencies
├── config.example.env               # Example configuration
├── .env                            # Your config (create this)
│
├── README.md                        # Full documentation
├── SETUP_GUIDE.md                  # Quick setup guide
├── PROJECT_OVERVIEW.md             # This file
│
└── src/
    ├── servers/                     # MCP Servers
    │   ├── gitlab_server.py        # GitLab API → MCP
    │   └── llm_server.py           # Ollama → MCP
    │
    ├── client/                      # Client Components
    │   ├── email_monitor.py        # Gmail monitoring
    │   └── orchestrator.py         # Workflow coordinator
    │
    └── utils/                       # Utilities
        ├── config.py               # Configuration
        └── gitlab_client.py        # GitLab API wrapper
```

## Components

### 1. GitLab MCP Server (`src/servers/gitlab_server.py`)
Exposes GitLab functionality via MCP protocol:
- `get_merge_request` - Fetch MR metadata
- `get_merge_request_changes` - Get diffs
- `get_merge_request_discussions` - Get comments
- `post_merge_request_note` - Post comment
- `parse_mr_url` - Parse URL

### 2. LLM MCP Server (`src/servers/llm_server.py`)
Wraps Ollama for code understanding:
- `summarize_code_changes` - Generate MR summary
- `answer_question` - General LLM query

### 3. Email Monitor (`src/client/email_monitor.py`)
Monitors Gmail for assignment notifications:
- IMAP-based polling
- Detects "was added as an assignee" emails
- Extracts GitLab MR URLs
- Tracks processed emails

### 4. Orchestrator (`src/client/orchestrator.py`)
MCP client that coordinates the workflow:
- Connects to both MCP servers
- Fetches MR details from GitLab
- Sends to LLM for summarization
- Posts summary back to GitLab

### 5. Main Service (`main.py`)
Ties everything together:
- Background email monitoring
- MR processing queue
- Graceful shutdown handling
- Logging and error handling

## Testing Individual Components

```bash
# Test email monitoring (one-time check)
python -m src.client.email_monitor

# Test orchestrator (manual MR URL)
python -m src.client.orchestrator

# Test GitLab MCP server
python -m src.servers.gitlab_server

# Test LLM MCP server
python -m src.servers.llm_server
```

## Configuration Required

Before running, you need:

1. **GitLab Personal Access Token**
   - Settings → Access Tokens
   - Scopes: `api`, `read_api`

2. **Gmail App Password**
   - Google Account → Security → App Passwords
   - Generate password for "Mail"

3. **Ollama Running**
   - `ollama serve`
   - `ollama pull codellama`

4. **Environment File**
   - Copy `config.example.env` to `.env`
   - Fill in your credentials

## How It Works

```
┌─────────────┐
│   Gmail     │  Email arrives: "X was added as assignee"
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│ Email Monitor   │  Detects assignment, extracts MR URL
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│  Orchestrator   │  Coordinates workflow
└─────┬───────┬───┘
      │       │
      ▼       ▼
┌─────────┐ ┌─────────┐
│ GitLab  │ │   LLM   │
│  MCP    │ │   MCP   │
│ Server  │ │ Server  │
└─────┬───┘ └────┬────┘
      │          │
      ▼          ▼
┌──────────┐ ┌──────────┐
│  GitLab  │ │  Ollama  │
│   API    │ │   API    │
└──────────┘ └──────────┘
```

## Next Steps

1. **Setup** - Follow [SETUP_GUIDE.md](SETUP_GUIDE.md)
2. **Test** - Run individual components
3. **Run** - Start the main service
4. **Monitor** - Check `gitlab_mr_summarizer.log`

## Customization

### Change Summary Format
Edit `src/servers/llm_server.py` → `_summarize_code_changes()`

### Modify Email Detection
Edit `src/client/email_monitor.py` → `_is_gitlab_assignment_email()`

### Add New MCP Tools
Add to `src/servers/gitlab_server.py` or `llm_server.py`

### Change Check Interval
Set `CHECK_INTERVAL` in `.env` (default: 60 seconds)

## Support

- **Full docs**: [README.md](README.md)
- **Quick setup**: [SETUP_GUIDE.md](SETUP_GUIDE.md)
- **Logs**: `gitlab_mr_summarizer.log`

## Architecture Highlights

✅ **MCP-based** - Modular, reusable servers
✅ **Local LLM** - Privacy-focused, no external APIs
✅ **Async** - Efficient background processing
✅ **Configurable** - Environment-based config
✅ **Tested** - Each component can be tested independently
✅ **Production-ready** - Logging, error handling, graceful shutdown

