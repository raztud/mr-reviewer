# GitLab MR Summarizer with MCP

An automated workflow system that monitors Gmail for GitLab assignment notifications, fetches merge request details via MCP servers, generates human-readable summaries using local LLMs (Ollama), and posts them as GitLab comments.

## Architecture

The system consists of 4 main components:

1. **Email Monitor** - Polls Gmail for GitLab assignment notifications
2. **GitLab MCP Server** - Exposes GitLab MR data via MCP protocol
3. **Local LLM MCP Server** - Wraps Ollama for code summarization via MCP
4. **Orchestrator** - MCP client that coordinates the workflow

## Features

- ✅ Automatic detection of GitLab assignment emails
- ✅ MCP-based architecture for modularity and reusability
- ✅ Local LLM summarization (privacy-focused, no data sent to external APIs)
- ✅ Automatic posting of summaries to GitLab MRs
- ✅ Duplicate detection to avoid reprocessing
- ✅ Background monitoring with configurable intervals
- ✅ Comprehensive logging

## Prerequisites

### 1. Python 3.9+

```bash
python --version  # Should be 3.9 or higher
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

### Running the Full Service

```bash
python main.py
```

This will:
1. Start monitoring your Gmail inbox
2. Detect GitLab assignment notifications
3. Process new MRs automatically
4. Post summaries to GitLab

Press `Ctrl+C` to stop.

### Testing Individual Components

#### Test GitLab MCP Server

```bash
python -m src.servers.gitlab_server
```

#### Test LLM MCP Server

```bash
python -m src.servers.llm_server
```

#### Test Email Monitor

```bash
python -m src.client.email_monitor
```

This will check your inbox once and display detected MRs.

#### Test Orchestrator

```bash
python -m src.client.orchestrator
```

You'll be prompted to enter a GitLab MR URL to test the full workflow.

## How It Works

### Workflow

1. **Email Detection**
   - Service polls Gmail every `CHECK_INTERVAL` seconds
   - Looks for emails containing "was added as an assignee"
   - Extracts GitLab MR URL from email body

2. **MR Processing**
   - Orchestrator receives MR URL from email monitor
   - Connects to GitLab MCP server to fetch:
     - MR metadata (title, description, author, branches)
     - Code changes (diffs)
     - Existing discussions

3. **Summary Generation**
   - Sends MR details to Local LLM MCP server
   - LLM analyzes code changes and generates human-readable summary
   - Summary includes:
     - High-level purpose
     - Key files modified
     - Important implementation details
     - Potential impact/risks

4. **Comment Posting**
   - Orchestrator posts summary to GitLab as a comment
   - Comment includes AI attribution and timestamp

### Data Flow

```
Gmail → Email Monitor → MR Queue → Orchestrator
                                        ↓
                            ┌───────────┴───────────┐
                            ↓                       ↓
                    GitLab MCP Server      LLM MCP Server
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
├── main.py                    # Main service entry point
├── requirements.txt           # Python dependencies
├── config.example.env         # Example configuration
├── .env                       # Your configuration (not in git)
├── README.md                  # This file
└── src/
    ├── servers/
    │   ├── gitlab_server.py   # GitLab MCP server
    │   └── llm_server.py      # Local LLM MCP server
    ├── client/
    │   ├── email_monitor.py   # Gmail monitoring service
    │   └── orchestrator.py    # MCP client orchestrator
    └── utils/
        ├── config.py          # Configuration management
        └── gitlab_client.py   # GitLab API wrapper
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
- Check email search criteria in `email_monitor.py`
- Verify GitLab sends emails with "was added as an assignee" text
- Look at `gitlab_mr_summarizer.log` for details
- Test manually: `python -m src.client.email_monitor`

### Summary Not Posted

**Solution:**
- Check GitLab token has write permissions
- Verify you have access to post comments on the MR
- Check logs for error details

## Logs

Logs are written to:
- Console (stdout)
- `gitlab_mr_summarizer.log` file

Set `LOG_LEVEL=DEBUG` for more verbose logging.

## Security Considerations

1. **Credentials**: Never commit `.env` file to git
2. **Tokens**: Use minimal required permissions for GitLab token
3. **Gmail**: Use app-specific password, not main password
4. **Local LLM**: All code is processed locally, no data sent externally

## Extending the System

### Adding New MCP Tools

Edit `src/servers/gitlab_server.py` or `src/servers/llm_server.py` and:

1. Add tool definition in `list_tools()`
2. Add handler in `call_tool()`

### Supporting Other Git Platforms

Create a new MCP server (e.g., `github_server.py`) following the same pattern as `gitlab_server.py`.

### Custom Summary Formats

Edit the prompt in `src/servers/llm_server.py` → `_summarize_code_changes()` method.

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

## License

This project is provided as-is for educational and personal use.

## Contributing

Feel free to submit issues or pull requests!

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review logs in `gitlab_mr_summarizer.log`
3. Open an issue with logs and configuration (redact sensitive data)

