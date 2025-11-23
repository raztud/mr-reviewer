"""MCP Client Orchestrator - Coordinates the workflow."""
import asyncio
import json
import logging
from typing import Optional, Dict, Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from ..utils.config import Config
from ..utils.gitlab_client import GitLabClient

logger = logging.getLogger(__name__)


class MCPOrchestrator:
    """Orchestrates the MR summarization workflow using MCP servers."""
    
    def __init__(self, config: Config):
        """Initialize orchestrator.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.gitlab_session: Optional[ClientSession] = None
        self.llm_session: Optional[ClientSession] = None
        self.gitlab_exit_stack = None
        self.llm_exit_stack = None
    
    async def start(self):
        """Start MCP client sessions."""
        logger.info("Starting MCP client sessions...")
        
        # Start GitLab MCP server
        gitlab_server = StdioServerParameters(
            command="python",
            args=["-m", "src.servers.gitlab_server"],
            env=None,
        )
        
        # Start LLM MCP server
        llm_server = StdioServerParameters(
            command="python",
            args=["-m", "src.servers.llm_server"],
            env=None,
        )
        
        # Create client sessions using async context managers
        self.gitlab_exit_stack = stdio_client(gitlab_server)
        gitlab_read, gitlab_write = await self.gitlab_exit_stack.__aenter__()
        
        self.llm_exit_stack = stdio_client(llm_server)
        llm_read, llm_write = await self.llm_exit_stack.__aenter__()
        
        self.gitlab_session = ClientSession(gitlab_read, gitlab_write)
        self.llm_session = ClientSession(llm_read, llm_write)
        
        # Initialize sessions
        await self.gitlab_session.initialize()
        await self.llm_session.initialize()
        
        logger.info("MCP client sessions started")
    
    async def stop(self):
        """Stop MCP client sessions."""
        logger.info("Stopping MCP client sessions...")
        
        # Close sessions
        if self.gitlab_session:
            try:
                await self.gitlab_session.__aexit__(None, None, None)
            except:
                pass
        
        if self.llm_session:
            try:
                await self.llm_session.__aexit__(None, None, None)
            except:
                pass
        
        # Close stdio clients
        if self.gitlab_exit_stack:
            try:
                await self.gitlab_exit_stack.__aexit__(None, None, None)
            except:
                pass
        
        if self.llm_exit_stack:
            try:
                await self.llm_exit_stack.__aexit__(None, None, None)
            except:
                pass
        
        logger.info("MCP client sessions stopped")
    
    async def process_merge_request(self, mr_url: str, email_subject: str = "", email_date: str = "") -> bool:
        """Process a merge request: fetch details, summarize, and post comment.
        
        Args:
            mr_url: GitLab MR URL
            email_subject: Email subject for context
            email_date: Email date for context
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Processing MR: {mr_url}")
            
            # Step 1: Parse MR URL
            logger.info("Step 1: Parsing MR URL...")
            parse_result = await self.gitlab_session.call_tool(
                "parse_mr_url",
                arguments={"url": mr_url}
            )
            
            if not parse_result or not parse_result.content:
                logger.error("Failed to parse MR URL")
                return False
            
            parsed_data = json.loads(parse_result.content[0].text)
            
            if "error" in parsed_data:
                logger.error(f"Error parsing MR URL: {parsed_data['error']}")
                return False
            
            project_id = parsed_data["project_id"]
            mr_iid = parsed_data["mr_iid"]
            
            logger.info(f"Parsed MR: project={project_id}, iid={mr_iid}")
            
            # Step 2: Fetch MR metadata
            logger.info("Step 2: Fetching MR metadata...")
            mr_result = await self.gitlab_session.call_tool(
                "get_merge_request",
                arguments={
                    "project_id": project_id,
                    "mr_iid": mr_iid,
                }
            )
            
            if not mr_result or not mr_result.content:
                logger.error("Failed to fetch MR metadata")
                return False
            
            mr_data = json.loads(mr_result.content[0].text)
            
            if "error" in mr_data:
                logger.error(f"Error fetching MR: {mr_data['error']}")
                return False
            
            logger.info(f"MR Title: {mr_data.get('title', 'N/A')}")
            logger.info(f"MR State: {mr_data.get('state', 'N/A')}")
            
            # Check if MR state is allowed for processing
            mr_state = mr_data.get("state", "").lower()
            allowed_states = self.config.mr_states_to_process
            if mr_state not in allowed_states:
                logger.info(f"⏭️  Skipping MR - state is '{mr_state}' (only processing: {', '.join(allowed_states)})")
                return False
            
            # Step 3: Fetch MR changes
            logger.info("Step 3: Fetching MR changes...")
            changes_result = await self.gitlab_session.call_tool(
                "get_merge_request_changes",
                arguments={
                    "project_id": project_id,
                    "mr_iid": mr_iid,
                }
            )
            
            if not changes_result or not changes_result.content:
                logger.error("Failed to fetch MR changes")
                return False
            
            changes_data = json.loads(changes_result.content[0].text)
            
            if "error" in changes_data:
                logger.error(f"Error fetching changes: {changes_data['error']}")
                return False
            
            logger.info(f"Files changed: {changes_data.get('diff_stats', {}).get('files_changed', 0)}")
            
            # Step 4: Generate summary using LLM
            logger.info("Step 4: Generating summary with LLM...")
            summary_result = await self.llm_session.call_tool(
                "summarize_code_changes",
                arguments={
                    "title": mr_data.get("title", ""),
                    "description": mr_data.get("description", ""),
                    "changes": changes_data.get("changes", []),
                    "source_branch": mr_data.get("source_branch", ""),
                    "target_branch": mr_data.get("target_branch", ""),
                }
            )
            
            if not summary_result or not summary_result.content:
                logger.error("Failed to generate summary")
                return False
            
            summary = summary_result.content[0].text
            logger.info(f"Generated summary ({len(summary)} chars)")
            
            # Step 5: Post summary as comment
            logger.info("Step 5: Posting summary to MR...")
            
            # Format the comment
            comment_body = f"""## 🤖 AI-Generated Summary

{summary}

---
*This summary was automatically generated by an AI assistant.*
*Notification received: {email_date}*
"""
            
            post_result = await self.gitlab_session.call_tool(
                "post_merge_request_note",
                arguments={
                    "project_id": project_id,
                    "mr_iid": mr_iid,
                    "body": comment_body,
                }
            )
            
            if not post_result or not post_result.content:
                logger.error("Failed to post comment")
                return False
            
            post_data = json.loads(post_result.content[0].text)
            
            if "error" in post_data:
                logger.error(f"Error posting comment: {post_data['error']}")
                return False
            
            logger.info(f"✅ Successfully posted summary to MR: {post_data.get('web_url', 'N/A')}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing MR: {e}", exc_info=True)
            return False


async def test_orchestrator():
    """Test orchestrator with a sample MR URL."""
    from ..utils.config import Config
    
    logging.basicConfig(level=logging.INFO)
    
    config = Config.from_env()
    errors = config.validate()
    if errors:
        logger.error(f"Configuration errors: {errors}")
        return
    
    orchestrator = MCPOrchestrator(config)
    
    try:
        await orchestrator.start()
        
        # Test with a sample MR URL (replace with actual URL)
        test_url = input("Enter GitLab MR URL to test: ")
        
        success = await orchestrator.process_merge_request(test_url)
        
        if success:
            print("\n✅ Test successful!")
        else:
            print("\n❌ Test failed!")
    
    finally:
        await orchestrator.stop()


if __name__ == "__main__":
    asyncio.run(test_orchestrator())

