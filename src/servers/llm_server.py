"""Local LLM MCP Server - Wraps Ollama for code summarization."""
import asyncio
import json
import logging
from typing import Any, Sequence

import aiohttp
from mcp.server import Server
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
from mcp.server.stdio import stdio_server

from src.utils.config import Config

logger = logging.getLogger(__name__)


class LocalLLMMCPServer:
    """MCP Server for local LLM operations via Ollama."""
    
    def __init__(self, config: Config):
        """Initialize Local LLM MCP server.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.ollama_url = config.ollama_base_url
        self.model = config.ollama_model
        self.server = Server("llm-server")
        
        # Register tool handlers
        self._register_handlers()
        logger.info("Local LLM server client initialized")

    async def _call_ollama(self, prompt: str, system: str = "") -> str:
        """Call Ollama API to generate text.
        
        Args:
            prompt: User prompt
            system: System prompt
            
        Returns:
            Generated text
        """
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
            }
            
            if system:
                payload["system"] = system
            
            try:
                async with session.post(
                    f"{self.ollama_url}/api/generate",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=300)  # 5 minutes timeout
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get("response", "")
                    else:
                        error_text = await response.text()
                        logger.error(f"Ollama API error: {response.status} - {error_text}")
                        return f"Error: Ollama API returned status {response.status}"
            except asyncio.TimeoutError:
                logger.error("Ollama API timeout")
                return "Error: Request to Ollama timed out"
            except Exception as e:
                logger.error(f"Error calling Ollama: {e}", exc_info=True)
                return f"Error: {str(e)}"
    
    def _register_handlers(self):
        """Register MCP tool handlers."""
        
        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """List available LLM tools."""
            return [
                Tool(
                    name="summarize_code_changes",
                    description="Generate a human-readable summary of code changes from a diff",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "title": {
                                "type": "string",
                                "description": "Merge request title",
                            },
                            "description": {
                                "type": "string",
                                "description": "Merge request description",
                            },
                            "changes": {
                                "type": "array",
                                "description": "List of file changes",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "old_path": {"type": "string"},
                                        "new_path": {"type": "string"},
                                        "diff": {"type": "string"},
                                    },
                                },
                            },
                            "source_branch": {
                                "type": "string",
                                "description": "Source branch name",
                            },
                            "target_branch": {
                                "type": "string",
                                "description": "Target branch name",
                            },
                        },
                        "required": ["title", "changes"],
                    },
                ),
                Tool(
                    name="answer_question",
                    description="Ask a general question to the LLM",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "question": {
                                "type": "string",
                                "description": "Question to ask",
                            },
                            "context": {
                                "type": "string",
                                "description": "Optional context for the question",
                            },
                        },
                        "required": ["question"],
                    },
                ),
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Any) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
            """Handle tool calls."""
            try:
                if name == "summarize_code_changes":
                    summary = await self._summarize_code_changes(arguments)
                    return [TextContent(type="text", text=summary)]
                
                elif name == "answer_question":
                    context = arguments.get("context", "")
                    prompt = arguments["question"]
                    if context:
                        prompt = f"Context:\n{context}\n\nQuestion: {prompt}"
                    
                    answer = await self._call_ollama(prompt)
                    return [TextContent(type="text", text=answer)]
                
                else:
                    return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]
                
            except Exception as e:
                logger.error(f"Error executing tool {name}: {e}", exc_info=True)
                return [TextContent(type="text", text=json.dumps({"error": str(e)}))]
    
    async def _summarize_code_changes(self, arguments: dict) -> str:
        """Generate a summary of code changes.
        
        Args:
            arguments: Dictionary with MR details and changes
            
        Returns:
            Human-readable summary
        """
        title = arguments.get("title", "")
        description = arguments.get("description", "")
        changes = arguments.get("changes", [])
        source_branch = arguments.get("source_branch", "")
        target_branch = arguments.get("target_branch", "")
        
        # Build a concise representation of changes
        files_summary = []
        total_diff_lines = 0
        
        for change in changes[:20]:  # Limit to first 20 files to avoid token limits
            old_path = change.get("old_path", "")
            new_path = change.get("new_path", "")
            diff = change.get("diff", "")
            
            # Count additions and deletions
            diff_lines = diff.split("\n")
            additions = len([l for l in diff_lines if l.startswith("+")])
            deletions = len([l for l in diff_lines if l.startswith("-")])
            
            total_diff_lines += len(diff_lines)
            
            # Truncate large diffs
            if len(diff) > 2000:
                diff = diff[:2000] + "\n... (truncated)"
            
            files_summary.append({
                "path": new_path or old_path,
                "additions": additions,
                "deletions": deletions,
                "diff": diff,
            })
        
        # Build prompt for LLM
        system_prompt = """You are a code review assistant. Your task is to summarize code changes in a clear, 
human-readable format. Focus on:
1. What the change does (high-level purpose)
2. Key files modified and their purpose
3. Important implementation details
4. Potential impact or risks

Format the summary in markdown with sections. Be concise but informative."""
        
        user_prompt = f"""Please summarize this merge request:

**Title:** {title}

**Description:**
{description if description else '(No description provided)'}

**Branch:** {source_branch} → {target_branch}

**Files Changed:** {len(changes)}

**Changed Files:**
"""
        
        for fs in files_summary:
            user_prompt += f"\n### {fs['path']}\n"
            user_prompt += f"- Additions: {fs['additions']}, Deletions: {fs['deletions']}\n"
            user_prompt += f"```diff\n{fs['diff']}\n```\n"
        
        if len(changes) > 20:
            user_prompt += f"\n... and {len(changes) - 20} more files\n"
        
        user_prompt += "\n\nProvide a clear, structured summary of these changes."
        
        # Call LLM
        summary = await self._call_ollama(user_prompt, system_prompt)
        
        return summary
    
    async def run(self):
        """Run the MCP server."""
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )


async def main():
    """Main entry point for Local LLM MCP server."""
    logging.basicConfig(level=logging.INFO)
    
    config = Config.from_env()
    
    server = LocalLLMMCPServer(config)
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())

