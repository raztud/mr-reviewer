"""GitLab MCP Server - Exposes GitLab API via MCP protocol."""
import asyncio
import json
import logging
from typing import Any, Sequence

from mcp.server import Server
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
from mcp.server.stdio import stdio_server

from src.utils.config import Config
from src.utils.gitlab_client import GitLabClient

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
        
        # Register tool handlers
        self._register_handlers()
        logger.info("GitLab server client initialized")
    
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
    
    async def run(self):
        """Run the MCP server."""
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )


async def main():
    """Main entry point for GitLab MCP server."""
    logging.basicConfig(level=logging.INFO)
    
    config = Config.from_env()
    errors = config.validate()
    if errors:
        logger.error(f"Configuration errors: {errors}")
        return
    
    server = GitLabMCPServer(config)
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())

