# GitLab MR Summarizer

An automated workflow system that monitors Gmail for GitLab assignment notifications, fetches merge request details via REST APIs, generates human-readable summaries using local LLMs (Ollama), and posts them as GitLab comments.

## Architecture

The system consists of 3 independent services:

1. **Email Monitor & Client** - Polls Gmail for GitLab assignment notifications and orchestrates the workflow
2. **GitLab REST API Server** - Exposes GitLab MR operations via HTTP/JSON (port 8001)
3. **LLM REST API Server** - Wraps Ollama for code summarization via HTTP/JSON (port 8002)

## Features

- ✅ Automatic detection of GitLab assignment emails
- ✅ REST API architecture - simple, stateless, and reliable
- ✅ Multi-process design - independent services for better stability
- ✅ Local LLM summarization (privacy-focused, no data sent to external APIs)
- ✅ Automatic posting of summaries to GitLab MRs
- ✅ Duplicate detection to avoid reprocessing
- ✅ Background monitoring with configurable intervals
- ✅ Comprehensive logging and easy debugging
- ✅ Comprehensive test suite with pytest

## Prerequisites

### 1. Python 3.11+

```bash
python --version  # Should be 3.11 or higher
```

### 2. Ollama (Local LLM)

Install Ollama from [ollama.ai](https://ollama.ai)

```bash
# Pull a code-focused model
ollama pull codellama
# OR
ollama pull deepseek-coder
# OR
ollama pull qwen2.5-coder
```

Start Ollama:
```bash
ollama serve
```

### 3. GitLab Personal Access Token

1. Go to GitLab → User Settings → Personal access tokens
2. Create a token with scopes: `api`, `read_api`, `write_repository`
3. Save the token securely

### 4. Gmail App Password

1. Enable 2-Factor Authentication on your Google account
2. Go to Google Account → Security → 2-Step Verification → App passwords
3. Generate an app password for "Mail"
4. Save the 16-character password

## Installation

### 1. Clone/Setup the Repository

```bash
cd /path/to/experiement-mcp
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

Copy the example configuration:

```bash
cp config.example.env .env
```

Edit `.env` with your credentials:

```env
# GitLab Configuration
GITLAB_URL=https://gitlab.com
GITLAB_TOKEN=glpat-xxxxxxxxxxxxxxxxxxxx

# Gmail Configuration
GMAIL_EMAIL=your_email@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx

# Ollama Configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=codellama

# Monitoring Configuration
CHECK_INTERVAL=60
LOG_LEVEL=INFO

# MR Processing Configuration
# Comma-separated list of MR states to process (opened, merged, closed)
MR_STATES_TO_PROCESS=opened

# Database for tracking processed emails
PROCESSED_EMAILS_DB=.processed_emails.json
```

## Usage

### Running All Services

Start all components (GitLab server, LLM server, and client):

```bash
make start-all
```

This will:
1. Start GitLab REST API server on port 8001
2. Start LLM REST API server on port 8002
3. Start email monitoring client
4. All services run in background with logs in `logs/` directory

### Viewing Logs

```bash
# View all logs
make logs

# Or view individual service logs
make logs-gitlab    # GitLab server logs
make logs-llm       # LLM server logs
make logs-client    # Client logs
```

### Stopping Services

```bash
make stop-all
```

### Checking Service Status

```bash
make status
```

### Development Mode (with tmux)

Run all services in a tmux session for easy monitoring:

```bash
make dev-all
```

This creates a tmux session with 3 panes (GitLab server, LLM server, client).
- Press `Ctrl+B` then `D` to detach
- Reattach with: `tmux attach -t gitlab-mr-summarizer`

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_email_monitor.py -v
```

## How It Works

### Workflow

1. **Email Detection**
   - Client polls Gmail every `CHECK_INTERVAL` seconds
   - Only processes emails received after service start time
   - Looks for emails containing "was added as an assignee"
   - Extracts GitLab MR URL from email body

2. **MR Validation**
   - Client checks MR state (only processes `opened` MRs by default)
   - Skips already merged or closed MRs

3. **MR Processing**
   - Client calls GitLab REST API server to fetch:
     - MR metadata (title, description, author, branches, state)
     - Code changes (diffs for all modified files)

4. **Summary Generation**
   - Client sends MR details to LLM REST API server
   - LLM server builds a structured prompt and calls Ollama
   - LLM analyzes code changes and generates human-readable summary
   - Summary includes:
     - High-level purpose
     - Key files modified
     - Important implementation details
     - Potential impact/risks

5. **Comment Posting**
   - Client posts summary to GitLab as a comment via REST API
   - Comment includes AI attribution and timestamp

### Data Flow

```
Gmail → Email Monitor → MR Queue → Client
                                      ↓
                          ┌───────────┴───────────┐
                          ↓ HTTP/JSON             ↓ HTTP/JSON
                  GitLab REST Server      LLM REST Server
                   (Port 8001)             (Port 8002)
                          ↓                       ↓
                     GitLab API              Ollama API
                          ↓                       ↓
                  MR Details & Diffs      Summary Generation
                          ↓                       ↓
                          └───────────┬───────────┘
                                      ↓
                          Post Comment to GitLab
```

## Project Structure

```
.
├── Makefile                        # Service management commands
├── requirements.txt                # Python dependencies
├── config.example.env              # Example configuration
├── .env                            # Your configuration (not in git)
├── README.md                       # This file
├── tests/                          # Test suite
│   └── test_email_monitor.py       # Email monitoring tests
├── logs/                           # Service logs (auto-created)
│   ├── gitlab_server.log
│   ├── llm_server.log
│   └── client.log
└── src/
    ├── servers/
    │   ├── gitlab_rest_server.py   # GitLab REST API server (port 8001)
    │   └── llm_rest_server.py      # LLM REST API server (port 8002)
    ├── client/
    │   ├── email_monitor.py        # Gmail monitoring service
    │   └── standalone_client.py    # Main client orchestrator
    └── utils/
        ├── config.py               # Configuration management
        └── gitlab_client.py        # GitLab API wrapper
```

## Configuration Options

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `GITLAB_URL` | GitLab instance URL | `https://gitlab.com` | No |
| `GITLAB_TOKEN` | Personal access token | - | Yes |
| `GMAIL_EMAIL` | Gmail address | - | Yes |
| `GMAIL_APP_PASSWORD` | App-specific password | - | Yes |
| `OLLAMA_BASE_URL` | Ollama API endpoint | `http://localhost:11434` | No |
| `OLLAMA_MODEL` | Model name | `codellama` | No |
| `CHECK_INTERVAL` | Email check interval (seconds) | `60` | No |
| `LOG_LEVEL` | Logging level | `INFO` | No |
| `MR_STATES_TO_PROCESS` | MR states to process (comma-separated) | `opened` | No |
| `PROCESSED_EMAILS_DB` | Processed emails database | `.processed_emails.json` | No |

### Recommended Ollama Models

- **codellama** - Good balance of speed and quality for code
- **deepseek-coder** - Better code understanding, larger model
- **qwen2.5-coder** - Fast and efficient
- **llama3.1** - General-purpose, good for summaries

## Troubleshooting

### Gmail Authentication Errors

**Error:** `Authentication failed`

**Solution:**
- Ensure 2FA is enabled on your Google account
- Use an app-specific password, not your regular password
- Check that IMAP is enabled in Gmail settings

### Ollama Connection Errors

**Error:** `Connection refused to localhost:11434`

**Solution:**
- Ensure Ollama is running: `ollama serve`
- Check that the model is pulled: `ollama list`
- Verify `OLLAMA_BASE_URL` in `.env`

### GitLab API Errors

**Error:** `401 Unauthorized`

**Solution:**
- Verify your GitLab token has correct scopes (`api`, `read_api`)
- Check token hasn't expired
- Ensure `GITLAB_URL` matches your GitLab instance

### No Emails Detected

**Solution:**
- Service only processes emails received AFTER it starts
- Check email search criteria in `email_monitor.py`
- Verify GitLab sends emails with "was added as an assignee" text
- Look at `logs/client.log` for details
- Check `make status` to ensure client is running

### Summary Not Posted

**Solution:**
- Check GitLab token has write permissions
- Verify you have access to post comments on the MR
- Check logs for error details

## Logs

Logs are written to `logs/` directory:
- `logs/gitlab_server.log` - GitLab REST API server
- `logs/llm_server.log` - LLM REST API server
- `logs/client.log` - Email monitor and orchestrator

View logs:
```bash
# All logs
make logs

# Individual service logs
make logs-gitlab
make logs-llm
make logs-client

# Or directly
tail -f logs/client.log
```

Set `LOG_LEVEL=DEBUG` in `.env` for more verbose logging.

## Security Considerations

1. **Credentials**: Never commit `.env` file to git
2. **Tokens**: Use minimal required permissions for GitLab token
3. **Gmail**: Use app-specific password, not main password
4. **Local LLM**: All code is processed locally, no data sent externally

## Extending the System

### Adding New REST API Endpoints

Edit `src/servers/gitlab_rest_server.py` or `src/servers/llm_rest_server.py`:

1. Add a new Pydantic model for request/response
2. Add a new FastAPI route (e.g., `@app.post("/api/...")`)
3. Implement the endpoint logic

### Supporting Other Git Platforms

Create a new REST server (e.g., `github_rest_server.py`) following the same pattern as `gitlab_rest_server.py`.

### Custom Summary Formats

Edit the prompt building in `src/servers/llm_rest_server.py` → `build_prompt()` function.

### Different Email Providers

Modify `src/client/email_monitor.py` to support other IMAP servers:

```python
mail = imaplib.IMAP4_SSL("imap.yourprovider.com")
```

## Performance

- **Email checking**: Configurable interval (default: 60s)
- **MR processing**: ~10-60 seconds depending on MR size and LLM model
- **Memory**: ~500MB-2GB depending on Ollama model
- **CPU**: Moderate during LLM inference, minimal otherwise

## Limitations

- Email polling (not real-time) - use Gmail webhooks for instant notifications
- Processes one MR at a time
- Large MRs (>20 files) are truncated to avoid token limits
- Requires Ollama running locally

## Future Enhancements

- [ ] Support for Gmail push notifications (webhooks)
- [ ] GitLab webhook integration (bypass email entirely)
- [ ] Multiple MR processing in parallel
- [ ] Web UI for monitoring and configuration
- [ ] Support for GitHub, Bitbucket
- [ ] Cloud LLM support (OpenAI, Anthropic)
- [ ] Custom summary templates
- [ ] Slack/Discord notifications
- [ ] Docker containerization
- [ ] Kubernetes deployment support

## License

This project is provided as-is for educational and personal use.

## Contributing

Feel free to submit issues or pull requests!

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review logs in `gitlab_mr_summarizer.log`
3. Open an issue with logs and configuration (redact sensitive data)

