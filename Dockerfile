# GitLab MR Summarizer - Python Services
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY config.example.env ./

# Create logs directory
RUN mkdir -p /app/logs

# Expose ports for the services
# 8001 - GitLab REST API
# 8002 - LLM REST API
EXPOSE 8001 8002

# Default command (can be overridden in docker-compose)
CMD ["python", "-m", "src.servers.gitlab_rest_server"]

