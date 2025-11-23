# Quick Setup Guide

## 5-Minute Setup

### Step 1: Install Ollama

```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.ai/install.sh | sh

# Windows
# Download from https://ollama.ai/download
```

Start Ollama and pull a model:

```bash
ollama serve &
ollama pull codellama
```

### Step 2: GitLab Token

1. Go to GitLab → Profile → Access Tokens
2. Name: `MR Summarizer`
3. Scopes: ✅ `api`, ✅ `read_api`
4. Click "Create personal access token"
5. **Copy the token** (you won't see it again!)

### Step 3: Gmail App Password

1. Go to [myaccount.google.com/security](https://myaccount.google.com/security)
2. Enable "2-Step Verification" (if not already enabled)
3. Search for "App passwords"
4. Select "Mail" and your device
5. **Copy the 16-character password**

### Step 4: Install & Configure

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create configuration
cp config.example.env .env
```

Edit `.env`:

```env
GITLAB_URL=https://gitlab.com
GITLAB_TOKEN=glpat-YOUR_TOKEN_HERE
GMAIL_EMAIL=your.email@gmail.com
GMAIL_APP_PASSWORD=your app password here
OLLAMA_MODEL=codellama
```

### Step 5: Run

```bash
python main.py
```

You should see:

```
GitLab MR Summarizer Service Starting...
✅ Service started successfully!
Monitoring for GitLab assignment notifications...
```

## Testing

Open another terminal:

```bash
# Test email monitoring
python -m src.client.email_monitor

# Test with a real MR URL
python -m src.client.orchestrator
# Enter a GitLab MR URL when prompted
```

## What Happens Next?

1. The service monitors your Gmail
2. When you receive "X was added as an assignee" email
3. It extracts the MR URL
4. Fetches MR details from GitLab
5. Generates summary using Ollama
6. Posts summary as comment on GitLab

## Troubleshooting

### Ollama not responding?

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Restart Ollama
pkill ollama
ollama serve &
```

### Gmail authentication failed?

- Make sure you're using the **app password**, not your regular password
- Enable IMAP in Gmail settings
- Check 2FA is enabled

### No emails detected?

- Send yourself a test GitLab notification
- Check the log file: `gitlab_mr_summarizer.log`
- Run test: `python -m src.client.email_monitor`

## Need Help?

Check the full [README.md](README.md) for detailed documentation.

