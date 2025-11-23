"""GitLab MCP Server - Standalone HTTP/SSE Server."""
import asyncio
import json
import logging
from typing import Any, Sequence

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
from starlette.applications import Starlette
from starlette.routing import Route

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.config import Config
from src.utils.gitlab_client import GitLabClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GitLabMCPServer:
    """MCP Server for GitLab operations."""
    
    def __init__(self, config: Config):
        """Initialize GitLab MCP server.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.gitlab_client = GitLabClient(config.gitlab_url, config.gitlab_token)
        self.server = Server("gitlab-server")
        self.sse = SseServerTransport("/messages")
        
        # Register tool handlers
        self._register_handlers()
    
    def _register_handlers(self):
        """Register MCP tool handlers."""
        
        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """List available GitLab tools."""
            return [
                Tool(
                    name="get_merge_request",
                    description="Fetch merge request metadata (title, description, author, etc.)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {
                                "type": "string",
                                "description": "GitLab project ID or path (e.g., 'group/project')",
                            },
                            "mr_iid": {
                                "type": "integer",
                                "description": "Merge request IID",
                            },
                        },
                        "required": ["project_id", "mr_iid"],
                    },
                ),
                Tool(
                    name="get_merge_request_changes",
                    description="Get merge request changes (diffs and changed files)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {
                                "type": "string",
                                "description": "GitLab project ID or path (e.g., 'group/project')",
                            },
                            "mr_iid": {
                                "type": "integer",
                                "description": "Merge request IID",
                            },
                        },
                        "required": ["project_id", "mr_iid"],
                    },
                ),
                Tool(
                    name="get_merge_request_discussions",
                    description="Fetch merge request discussions and comments",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {
                                "type": "string",
                                "description": "GitLab project ID or path (e.g., 'group/project')",
                            },
                            "mr_iid": {
                                "type": "integer",
                                "description": "Merge request IID",
                            },
                        },
                        "required": ["project_id", "mr_iid"],
                    },
                ),
                Tool(
                    name="post_merge_request_note",
                    description="Post a comment/note to a merge request",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {
                                "type": "string",
                                "description": "GitLab project ID or path (e.g., 'group/project')",
                            },
                            "mr_iid": {
                                "type": "integer",
                                "description": "Merge request IID",
                            },
                            "body": {
                                "type": "string",
                                "description": "Comment text (supports markdown)",
                            },
                        },
                        "required": ["project_id", "mr_iid", "body"],
                    },
                ),
                Tool(
                    name="parse_mr_url",
                    description="Parse GitLab MR URL to extract project ID and MR IID",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "GitLab merge request URL",
                            },
                        },
                        "required": ["url"],
                    },
                ),
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Any) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
            """Handle tool calls."""
            try:
                if name == "get_merge_request":
                    result = self.gitlab_client.get_merge_request(
                        arguments["project_id"],
                        arguments["mr_iid"]
                    )
                    return [TextContent(type="text", text=json.dumps(result, indent=2))]
                
                elif name == "get_merge_request_changes":
                    result = self.gitlab_client.get_merge_request_changes(
                        arguments["project_id"],
                        arguments["mr_iid"]
                    )
                    return [TextContent(type="text", text=json.dumps(result, indent=2))]
                
                elif name == "get_merge_request_discussions":
                    result = self.gitlab_client.get_merge_request_discussions(
                        arguments["project_id"],
                        arguments["mr_iid"]
                    )
                    return [TextContent(type="text", text=json.dumps(result, indent=2))]
                
                elif name == "post_merge_request_note":
                    result = self.gitlab_client.post_merge_request_note(
                        arguments["project_id"],
                        arguments["mr_iid"],
                        arguments["body"]
                    )
                    return [TextContent(type="text", text=json.dumps(result, indent=2))]
                
                elif name == "parse_mr_url":
                    result = GitLabClient.parse_mr_url(arguments["url"])
                    if result:
                        return [TextContent(
                            type="text",
                            text=json.dumps({
                                "project_id": result[0],
                                "mr_iid": result[1]
                            }, indent=2)
                        )]
                    else:
                        return [TextContent(
                            type="text",
                            text=json.dumps({"error": "Failed to parse MR URL"}, indent=2)
                        )]
                
                else:
                    return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]
                
            except Exception as e:
                logger.error(f"Error executing tool {name}: {e}", exc_info=True)
                return [TextContent(type="text", text=json.dumps({"error": str(e)}))]
    
    def create_app(self) -> Starlette:
        """Create Starlette app with SSE transport."""
        async def handle_sse(request):
            async with self.sse.connect_sse(
                request.scope,
                request.receive,
                request._send
            ) as streams:
                await self.server.run(
                    streams[0],
                    streams[1],
                    self.server.create_initialization_options()
                )
        
        async def handle_messages(request):
            await self.sse.handle_post_message(request.scope, request.receive, request._send)
        
        return Starlette(
            routes=[
                Route("/sse", endpoint=handle_sse),
                Route("/messages", endpoint=handle_messages, methods=["POST"]),
            ]
        )


async def main():
    """Main entry point for GitLab MCP server."""
    config = Config.from_env()
    errors = config.validate()
    if errors:
        logger.error(f"Configuration errors: {errors}")
        return
    
    server = GitLabMCPServer(config)
    app = server.create_app()
    
    import uvicorn
    
    logger.info("=" * 60)
    logger.info("GitLab MCP Server Starting...")
    logger.info(f"URL: http://localhost:8001")
    logger.info(f"SSE endpoint: http://localhost:8001/sse")
    logger.info("=" * 60)
    
    config = uvicorn.Config(app, host="0.0.0.0", port=8001, log_level="info")
    server_instance = uvicorn.Server(config)
    await server_instance.serve()


if __name__ == "__main__":
    asyncio.run(main())

