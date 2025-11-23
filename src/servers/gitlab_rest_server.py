#!/usr/bin/env python3
"""Simple REST API server for GitLab operations (non-MCP)."""

import json
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import uvicorn

from src.utils.config import Config
from src.utils.gitlab_client import GitLabClient

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load config
config = Config.from_env()

# Initialize GitLab client
gitlab_client = GitLabClient(config.gitlab_url, config.gitlab_token)

# Create FastAPI app
app = FastAPI(title="GitLab MR API", version="1.0.0")


class MRRequest(BaseModel):
    """Request model for MR operations."""
    project_id: str
    mr_iid: int


class PostNoteRequest(BaseModel):
    """Request model for posting a note."""
    project_id: str
    mr_iid: int
    body: str


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "gitlab-api"}


@app.post("/api/mr/get")
async def get_merge_request(request: MRRequest):
    """Get merge request metadata."""
    try:
        logger.info(f"Getting MR: {request.project_id}!{request.mr_iid}")
        result = gitlab_client.get_merge_request(request.project_id, request.mr_iid)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Error getting MR: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/mr/changes")
async def get_merge_request_changes(request: MRRequest):
    """Get merge request changes/diffs."""
    try:
        logger.info(f"Getting MR changes: {request.project_id}!{request.mr_iid}")
        result = gitlab_client.get_merge_request_changes(request.project_id, request.mr_iid)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Error getting MR changes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/mr/post_note")
async def post_merge_request_note(request: PostNoteRequest):
    """Post a note/comment to a merge request."""
    try:
        logger.info(f"Posting note to MR: {request.project_id}!{request.mr_iid}")
        result = gitlab_client.post_merge_request_note(
            request.project_id,
            request.mr_iid,
            request.body
        )
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Error posting note: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    logger.info("=" * 80)
    logger.info("Starting GitLab REST API Server")
    logger.info("=" * 80)
    logger.info(f"GitLab URL: {config.gitlab_url}")
    logger.info("Listening on: http://0.0.0.0:8001")
    logger.info("=" * 80)
    
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")

