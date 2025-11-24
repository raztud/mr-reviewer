# Docker Deployment Guide

This guide explains how to run the GitLab MR Summarizer using Docker and Docker Compose.

## Prerequisites

1. **Docker** and **Docker Compose** installed
2. **Ollama** running on your host machine (for LLM)
3. GitLab personal access token
4. Gmail app password

## Quick Start

### 1. Configure Environment Variables

Copy the example environment file:

```bash
cp .env.docker.example .env
```

Edit `.env` with your credentials:

```env
GITLAB_TOKEN=glpat-xxxxxxxxxxxxxxxxxxxx
GMAIL_EMAIL=your_email@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
```

### 2. Build and Start Services

Build the Docker image and start all services:

```bash
docker-compose up -d
```

This will start:
- **gitlab-server** on port 8001
- **llm-server** on port 8002
- **client** (email monitor)

### 3. View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f client
docker-compose logs -f gitlab-server
docker-compose logs -f llm-server

# Tail last 100 lines
docker-compose logs --tail=100 -f
```

### 4. Check Service Status

```bash
docker-compose ps
```

### 5. Stop Services

```bash
docker-compose down
```

## Architecture

```
┌─────────────────────────────────────┐
│  Host Machine                        │
│  ┌─────────────┐                    │
│  │   Ollama    │                    │
│  │  :11434     │                    │
│  └──────▲──────┘                    │
│         │                            │
│  ┌──────┴──────────────────────┐   │
│  │  Docker Network             │   │
│  │                              │   │
│  │  ┌──────────────┐           │   │
│  │  │ gitlab-server│:8001      │   │
│  │  └──────▲───────┘           │   │
│  │         │                    │   │
│  │  ┌──────┴───────┐           │   │
│  │  │  llm-server  │:8002      │   │
│  │  └──────▲───────┘           │   │
│  │         │                    │   │
│  │  ┌──────┴───────┐           │   │
│  │  │    client    │           │   │
│  │  └──────────────┘           │   │
│  └──────────────────────────────┘   │
└─────────────────────────────────────┘
```

## Environment Variables

All environment variables from `.env` are automatically passed to the containers.

### Required Variables

- `GITLAB_TOKEN` - GitLab personal access token
- `GMAIL_EMAIL` - Gmail address
- `GMAIL_APP_PASSWORD` - Gmail app-specific password

### Optional Variables

- `GITLAB_URL` - GitLab instance URL (default: https://gitlab.com)
- `GITLAB_FROM_EMAIL` - GitLab sender email (default: gitlab@mg.gitlab.com)
- `OLLAMA_BASE_URL` - Ollama API URL (default: http://host.docker.internal:11434)
- `OLLAMA_MODEL` - LLM model name (default: codellama)
- `CHECK_INTERVAL` - Email check interval in seconds (default: 60)
- `LOG_LEVEL` - Logging level (default: INFO)
- `MR_STATES_TO_PROCESS` - MR states to process (default: opened)
- `MAX_FILES_IN_PROMPT` - Max files in LLM prompt (default: 999999)
- `MAX_DIFF_LINES_PER_FILE` - Max diff lines per file (default: 999999)

## Accessing Ollama from Docker

By default, the LLM server connects to Ollama running on the host machine using `host.docker.internal:11434`.

### macOS/Windows

The default configuration works out of the box:

```env
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

### Linux

On Linux, you need to add `--add-host=host.docker.internal:host-gateway` or use your host IP:

```env
OLLAMA_BASE_URL=http://192.168.1.100:11434
```

Or modify docker-compose.yml:

```yaml
extra_hosts:
  - "host.docker.internal:172.17.0.1"
```

## Volume Mounts

The following directories are mounted:

- `./logs:/app/logs` - Service logs
- `./.processed_emails.json:/app/.processed_emails.json` - Processed emails database

Logs are accessible from your host machine in the `logs/` directory.

## Health Checks

The GitLab and LLM servers have health check endpoints:

```bash
# Check GitLab server
curl http://localhost:8001/health

# Check LLM server
curl http://localhost:8002/health
```

Response:
```json
{
  "status": "healthy",
  "service": "gitlab-api"
}
```

## Troubleshooting

### Container won't start

Check logs:
```bash
docker-compose logs client
```

Common issues:
- Missing environment variables
- Incorrect GitLab token
- Gmail authentication failure

### Can't connect to Ollama

**Error**: `Connection refused to localhost:11434`

**Solutions**:
1. Ensure Ollama is running on host: `ollama serve`
2. Check `OLLAMA_BASE_URL` uses `host.docker.internal`
3. On Linux, use your host IP instead

### Services keep restarting

Check if all required environment variables are set:
```bash
docker-compose config
```

### View container resource usage

```bash
docker stats
```

## Development

### Rebuild after code changes

```bash
docker-compose down
docker-compose build
docker-compose up -d
```

### Run in foreground (see logs immediately)

```bash
docker-compose up
```

### Execute commands in running container

```bash
# Open shell in client container
docker-compose exec client bash

# Check Python version
docker-compose exec client python --version

# View processed emails
docker-compose exec client cat .processed_emails.json
```

## Production Deployment

### Using Docker Swarm

```bash
docker stack deploy -c docker-compose.yml gitlab-mr-summarizer
```

### Using Kubernetes

Convert docker-compose to Kubernetes manifests using Kompose:

```bash
kompose convert -f docker-compose.yml
kubectl apply -f .
```

### Resource Limits

Add resource limits in docker-compose.yml:

```yaml
services:
  client:
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 512M
        reservations:
          memory: 256M
```

## Scaling

To run multiple clients (not recommended, will process duplicates):

```bash
docker-compose up -d --scale client=3
```

## Backup

Backup the processed emails database:

```bash
docker-compose exec client cat .processed_emails.json > backup_$(date +%Y%m%d).json
```

## Clean Up

Remove all containers, networks, and images:

```bash
# Stop and remove containers
docker-compose down

# Also remove volumes
docker-compose down -v

# Remove images
docker-compose down --rmi all
```

## Updates

Pull latest code and rebuild:

```bash
git pull
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## Monitoring

### With Prometheus/Grafana

Add health check metrics and expose them for scraping.

### With Portainer

Manage containers via web UI:

```bash
docker run -d -p 9000:9000 --name portainer \
  -v /var/run/docker.sock:/var/run/docker.sock \
  portainer/portainer-ce
```

Access at: http://localhost:9000

## Security

1. **Never commit `.env` file** - it contains secrets
2. **Use secrets management** in production (Docker Secrets, Vault)
3. **Run as non-root user** (add to Dockerfile):
   ```dockerfile
   RUN useradd -m -u 1000 appuser
   USER appuser
   ```
4. **Scan images** for vulnerabilities:
   ```bash
   docker scan gitlab-mr-summarizer
   ```

## Support

For issues with Docker deployment:
1. Check logs: `docker-compose logs`
2. Verify environment variables: `docker-compose config`
3. Check service health: `curl http://localhost:8001/health`
4. Review Docker.md for troubleshooting steps

