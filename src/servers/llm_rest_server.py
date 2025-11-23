#!/usr/bin/env python3
"""Simple REST API server for LLM operations (non-MCP)."""

import json
import logging
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
import uvicorn

from src.utils.config import Config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load config
config = Config.from_env()

# Create FastAPI app
app = FastAPI(title="LLM Summarizer API", version="1.0.0")


class SummarizeRequest(BaseModel):
    """Request model for code summarization."""
    title: str
    description: str
    changes: List[Dict[str, Any]]
    source_branch: str
    target_branch: str


def build_prompt(title: str, description: str, changes: List[Dict], source_branch: str, target_branch: str) -> str:
    """Build the prompt for the LLM."""
    prompt = f"""You are a code review assistant. Please provide a concise, human-readable summary of the following merge request.

**Merge Request Title:** {title}

**Description:**
{description or "No description provided."}

**Branches:** `{source_branch}` → `{target_branch}` 

**Changes:**
"""
    
    # Add file changes
    for change in changes[:10]:  # Limit to first 10 files
        old_path = change.get("old_path", "")
        new_path = change.get("new_path", "")
        diff = change.get("diff", "")
        
        if new_path == old_path:
            prompt += f"\n### File: `{new_path}`\n"
        else:
            prompt += f"\n### File: `{old_path}` → `{new_path}`\n"
        
        # Add truncated diff
        diff_lines = diff.split("\n")[:50]  # First 50 lines
        prompt += "```diff\n"
        prompt += "\n".join(diff_lines)
        if len(diff.split("\n")) > 50:
            prompt += "\n... (diff truncated)"
        prompt += "\n```\n"
    
    if len(changes) > 10:
        prompt += f"\n... and {len(changes) - 10} more files.\n"
    
    prompt += """

Please provide a summary that includes:
1. **Overview**: What is the main purpose of this MR?
2. **Key Changes**: What are the most important changes?
3. **Impact**: What areas of the codebase are affected?

Keep the summary concise (3-5 sentences max) and focus on what reviewers need to know.
"""
    
    return prompt


def call_ollama(prompt: str) -> str:
    """Call Ollama API to generate summary."""
    try:
        response = requests.post(
            f"{config.ollama_base_url}/api/generate",
            json={
                "model": config.ollama_model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "num_predict": 500,
                }
            },
            timeout=120  # 2 minutes timeout
        )
        response.raise_for_status()
        result = response.json()
        return result.get("response", "")
    except Exception as e:
        logger.error(f"Error calling Ollama: {e}")
        raise


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "llm-api", "model": config.ollama_model}


@app.post("/api/summarize")
async def summarize_code_changes(request: SummarizeRequest):
    """Summarize code changes using LLM."""
    try:
        logger.info(f"Summarizing MR: {request.title}")
        logger.info(f"Files changed: {len(request.changes)}")
        
        # Build prompt
        prompt = build_prompt(
            request.title,
            request.description,
            request.changes,
            request.source_branch,
            request.target_branch
        )
        
        logger.info(f"Prompt length: {len(prompt)} chars")
        
        # Call Ollama
        summary = call_ollama(prompt)
        
        logger.info(f"Generated summary: {len(summary)} chars")
        
        return {"success": True, "summary": summary}
    except Exception as e:
        logger.error(f"Error summarizing changes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    logger.info("=" * 80)
    logger.info("Starting LLM REST API Server")
    logger.info("=" * 80)
    logger.info(f"Ollama URL: {config.ollama_base_url}")
    logger.info(f"Model: {config.ollama_model}")
    logger.info("Listening on: http://0.0.0.0:8002")
    logger.info("=" * 80)
    
    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="info")

