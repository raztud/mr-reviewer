#!/usr/bin/env python3
"""Simple REST API server for LLM operations (non-MCP)."""

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


def build_prompt_summarize(title: str, description: str, changes: List[Dict], source_branch: str, target_branch: str, max_files: int = 999999, max_lines: int = 999999) -> str:
    """Build the prompt for the LLM.
    
    Args:
        max_files: Maximum number of files to include (default: no limit)
        max_lines: Maximum diff lines per file (default: no limit)
    """
    prompt = f"""You are a code review assistant. Please provide a concise, human-readable summary of the following merge request.

**Merge Request Title:** {title}

**Description:**
{description or "No description provided."}

**Branches:** `{source_branch}` → `{target_branch}` 

**Changes:**
"""
    
    # Add file changes
    files_to_process = min(len(changes), max_files)
    for change in changes[:files_to_process]:
        old_path = change.get("old_path", "")
        new_path = change.get("new_path", "")
        diff = change.get("diff", "")
        
        if new_path == old_path:
            prompt += f"\n### File: `{new_path}`\n"
        else:
            prompt += f"\n### File: `{old_path}` → `{new_path}`\n"
        
        # Add diff (potentially truncated)
        diff_lines = diff.split("\n")
        lines_to_include = min(len(diff_lines), max_lines)
        prompt += "```diff\n"
        prompt += "\n".join(diff_lines[:lines_to_include])
        if len(diff_lines) > max_lines:
            prompt += f"\n... (diff truncated: {len(diff_lines) - max_lines} more lines)"
        prompt += "\n```\n"
    
    if len(changes) > files_to_process:
        prompt += f"\n... and {len(changes) - files_to_process} more files.\n"
    
    prompt += """

Please provide a summary that includes:
1. **Overview**: What is the main purpose of this MR?
2. **Key Changes**: What are the most important changes?
3. **Impact**: What areas of the codebase are affected?

Keep the summary concise (3-5 sentences max) and focus on what reviewers need to know.
"""
    
    return prompt


def build_prompt_review(
        title: str,
        description: str,
        changes: List[Dict],
        source_branch: str,
        target_branch: str,
        max_files: int = 999999,
        max_lines: int = 999999
) -> str:
    """Build the prompt for the LLM.
    
    Args:
        max_files: Maximum number of files to include (default: no limit)
        max_lines: Maximum diff lines per file (default: no limit)
    """
    prompt = f"""Act as a peer senior software engineer reviewer and add do a Merge Request review: 
- Design & Architecture: Are the abstractions, boundaries, and responsibilities reasonable? Any better patterns or simplifications you'd suggest?
- Correctness & Edge Cases: Potential bugs, missing edge cases, or unclear behavior to question in review comments.
- Performance & Scalability: Any hot paths, N+1 patterns, unnecessary allocations, or operations that may not scale?
- Security & Reliability: Possible security issues, validation concerns, error handling gaps, or robustness problems.
- Testing: What tests are present, what's missing, and concrete suggestions for additional unit/integration/e2e tests.
- Readability & Maintainability: Naming, structure, duplication, comments, and how easy it will be to maintain this in the future.
- Risk Assessment: Overall risk level (low/medium/high) and what to watch out for during rollout.
- Use concise bullet points. Be honest and critical but constructive, as if you are leaving review comments for a teammate. Do not invent features that are not in the diff.
You can skip any of these points if they don't make sense or the specific points are not affected in the MR.

**Merge Request Title:** {title}

**Description:**
{description or "No description provided."}

**Branches:** `{source_branch}` → `{target_branch}` 

**Changes:**
"""

    # Add file changes
    files_to_process = min(len(changes), max_files)
    for change in changes[:files_to_process]:
        old_path = change.get("old_path", "")
        new_path = change.get("new_path", "")
        diff = change.get("diff", "")

        if new_path == old_path:
            prompt += f"\n### File: `{new_path}`\n"
        else:
            prompt += f"\n### File: `{old_path}` → `{new_path}`\n"

        # Add diff (potentially truncated)
        diff_lines = diff.split("\n")
        lines_to_include = min(len(diff_lines), max_lines)
        prompt += "```diff\n"
        prompt += "\n".join(diff_lines[:lines_to_include])
        if len(diff_lines) > max_lines:
            prompt += f"\n... (diff truncated: {len(diff_lines) - max_lines} more lines)"
        prompt += "\n```\n"

    if len(changes) > files_to_process:
        prompt += f"\n... and {len(changes) - files_to_process} more files.\n"

    prompt += """

Keep the sentences concise and focus on what the developer needs to know.
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
        
        # Build prompt (with configured limits)
        prompt = build_prompt_summarize(
            request.title,
            request.description,
            request.changes,
            request.source_branch,
            request.target_branch,
            max_files=config.max_files_in_prompt,
            max_lines=config.max_diff_lines_per_file
        )
        
        logger.info(f"Prompt length: {len(prompt)} chars")
        
        # Call Ollama
        summary = call_ollama(prompt)
        
        logger.info(f"Generated summary: {len(summary)} chars")
        
        return {"success": True, "summary": summary}
    except Exception as e:
        logger.error(f"Error summarizing changes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/review")
async def summarize_code_changes(request: SummarizeRequest):
    """Review code changes using LLM."""
    try:
        logger.info(f"Summarizing MR: {request.title}")
        logger.info(f"Files changed: {len(request.changes)}")

        # Build prompt (with configured limits)
        prompt = build_prompt_review(
            request.title,
            request.description,
            request.changes,
            request.source_branch,
            request.target_branch,
            max_files=config.max_files_in_prompt,
            max_lines=config.max_diff_lines_per_file
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

