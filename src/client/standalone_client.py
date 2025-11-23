"""Standalone client - Connects to network MCP servers."""
import asyncio
import logging
import signal

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.config import Config
from src.utils.gitlab_client import GitLabClient
from src.client.email_monitor import EmailMonitor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('gitlab_mr_summarizer.log'),
    ]
)

logger = logging.getLogger(__name__)


class StandaloneOrchestrator:
    """Orchestrator that connects to network MCP servers."""
    
    def __init__(self, config: Config):
        """Initialize orchestrator.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.gitlab_url = "http://localhost:8001"
        self.llm_url = "http://localhost:8002"
    
    async def process_merge_request(self, mr_url: str, email_subject: str = "", email_date: str = "") -> bool:
        """Process a merge request: fetch details, summarize, and post comment.
        
        Args:
            mr_url: GitLab MR URL
            mr_subject: Email subject for context
            email_date: Email date for context
            
        Returns:
            True if successful, False otherwise
        """
        try:
            import aiohttp
            
            logger.info(f"Processing MR: {mr_url}")
            
            # Step 1: Parse MR URL using GitLab client
            logger.info("Step 1: Parsing MR URL...")
            parsed = GitLabClient.parse_mr_url(mr_url)
            if not parsed:
                logger.error("Failed to parse MR URL")
                return False
            
            project_id, mr_iid = parsed
            logger.info(f"Parsed MR: project={project_id}, iid={mr_iid}")
            
            # Step 2: Fetch MR metadata via REST API
            logger.info("Step 2: Fetching MR metadata...")
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.gitlab_url}/api/mr/get",
                    json={
                        "project_id": project_id,
                        "mr_iid": mr_iid,
                    }
                ) as response:
                    result = await response.json()
                    if not result.get("success"):
                        raise Exception("Failed to fetch MR metadata")
                    mr_data = result["data"]
            
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
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.gitlab_url}/api/mr/changes",
                    json={
                        "project_id": project_id,
                        "mr_iid": mr_iid,
                    }
                ) as response:
                    result = await response.json()
                    if not result.get("success"):
                        raise Exception("Failed to fetch MR changes")
                    changes_data = result["data"]
            
            if "error" in changes_data:
                logger.error(f"Error fetching changes: {changes_data['error']}")
                return False
            
            logger.info(f"Files changed: {changes_data.get('diff_stats', {}).get('files_changed', 0)}")
            
            # Step 4: Generate summary using LLM
            logger.info("Step 4: Generating summary with LLM...")
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.llm_url}/api/summarize",
                    json={
                        "title": mr_data.get("title", ""),
                        "description": mr_data.get("description", ""),
                        "changes": changes_data.get("changes", []),
                        "source_branch": mr_data.get("source_branch", ""),
                        "target_branch": mr_data.get("target_branch", ""),
                    }
                ) as response:
                    result = await response.json()
                    if not result.get("success"):
                        raise Exception("Failed to generate summary")
                    summary = result["summary"]
            
            logger.info(f"Generated summary ({len(summary)} chars)")
            
            # Step 5: Post summary as comment
            logger.info("Step 5: Posting summary to MR...")
            
            comment_body = f"""## 🤖 AI-Generated Summary

{summary}

---
*This summary was automatically generated by an AI assistant.*
*Notification received: {email_date}*
"""
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.gitlab_url}/api/mr/post_note",
                    json={
                        "project_id": project_id,
                        "mr_iid": mr_iid,
                        "body": comment_body,
                    }
                ) as response:
                    result = await response.json()
                    if not result.get("success"):
                        raise Exception("Failed to post comment")
                    post_data = result["data"]
            
            if "error" in post_data:
                logger.error(f"Error posting comment: {post_data['error']}")
                return False
            
            logger.info(f"✅ Successfully posted summary to MR: {post_data.get('web_url', 'N/A')}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing MR: {e}", exc_info=True)
            return False


class StandaloneClient:
    """Standalone client for GitLab MR summarization."""
    
    def __init__(self, config: Config):
        """Initialize client.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.orchestrator = StandaloneOrchestrator(config)
        self.email_monitor = EmailMonitor(config, self.on_mr_detected)
        self.running = False
        self.mr_queue = None
        self.shutdown_event = None
    
    async def on_mr_detected(self, mr_url: str, email_subject: str, email_date: str):
        """Callback when MR assignment detected."""
        logger.info(f"New MR detected: {mr_url}")
        if self.mr_queue:
            await self.mr_queue.put({
                "url": mr_url,
                "subject": email_subject,
                "date": email_date,
            })
    
    async def process_queue(self):
        """Process MR queue."""
        logger.info("Starting MR queue processor...")
        
        try:
            while self.running:
                try:
                    mr_info = await asyncio.wait_for(self.mr_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                
                logger.info(f"Processing MR from queue: {mr_info['url']}")
                
                success = await self.orchestrator.process_merge_request(
                    mr_info["url"],
                    mr_info["subject"],
                    mr_info["date"]
                )
                
                if success:
                    logger.info(f"✅ Successfully processed MR: {mr_info['url']}")
                else:
                    logger.error(f"❌ Failed to process MR: {mr_info['url']}")
                
                self.mr_queue.task_done()
                
        except asyncio.CancelledError:
            logger.info("MR queue processor stopped")
            raise
    
    async def start(self):
        """Start the client."""
        logger.info("=" * 60)
        logger.info("GitLab MR Summarizer Standalone Client Starting...")
        logger.info("=" * 60)
        
        # Create async resources
        self.mr_queue = asyncio.Queue()
        self.shutdown_event = asyncio.Event()
        
        # Setup signal handlers
        loop = asyncio.get_running_loop()
        
        def signal_handler():
            logger.info("Received shutdown signal")
            self.running = False
            self.shutdown_event.set()
        
        loop.add_signal_handler(signal.SIGTERM, signal_handler)
        loop.add_signal_handler(signal.SIGINT, signal_handler)
        logger.info("Signal handlers registered")
        
        # Validate configuration
        errors = self.config.validate()
        if errors:
            logger.error("Configuration errors:")
            for error in errors:
                logger.error(f"  - {error}")
            return
        
        logger.info(f"GitLab URL: {self.config.gitlab_url}")
        logger.info(f"Email: {self.config.gmail_email}")
        logger.info(f"Check Interval: {self.config.check_interval}s")
        logger.info(f"GitLab MCP Server: http://localhost:8001")
        logger.info(f"LLM MCP Server: http://localhost:8002")
        logger.info("=" * 60)
        
        self.running = True
        
        try:
            # Start background tasks
            email_task = asyncio.create_task(self.email_monitor.start_monitoring())
            queue_task = asyncio.create_task(self.process_queue())
            self.tasks = [email_task, queue_task]
            
            logger.info("✅ Client started successfully!")
            logger.info("Monitoring for GitLab assignment notifications...")
            logger.info("Press Ctrl+C to stop.")
            
            # Wait for shutdown
            await self.shutdown_event.wait()
            
            # Cancel tasks
            logger.info("Cancelling background tasks...")
            for task in self.tasks:
                if not task.done():
                    task.cancel()
            
            await asyncio.gather(*self.tasks, return_exceptions=True)
            logger.info("Background tasks stopped")
            
        except asyncio.CancelledError:
            logger.info("Client cancelled")
        except Exception as e:
            logger.error(f"Error in client: {e}", exc_info=True)
        finally:
            logger.info("Client stopped")


async def main():
    """Main entry point."""
    config = Config.from_env()
    client = StandaloneClient(config)
    
    try:
        await client.start()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        logger.info("Cleanup complete")


if __name__ == "__main__":
    asyncio.run(main())

