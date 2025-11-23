"""Main service - GitLab MR Summarizer."""
import asyncio
import logging
import signal
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.utils.config import Config
from src.client.email_monitor import EmailMonitor
from src.client.orchestrator import MCPOrchestrator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('gitlab_mr_summarizer.log'),
    ]
)

logger = logging.getLogger(__name__)


class GitLabMRSummarizer:
    """Main service for GitLab MR summarization."""
    
    def __init__(self, config: Config):
        """Initialize service.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.orchestrator = MCPOrchestrator(config)
        self.email_monitor = EmailMonitor(config, self.on_mr_detected)
        self.running = False
        self.mr_queue = None  # Created in async context
        self.tasks = []
        self.shutdown_event = None  # Created in async context
    
    async def on_mr_detected(self, mr_url: str, email_subject: str, email_date: str):
        """Callback when a new MR assignment is detected.
        
        Args:
            mr_url: GitLab MR URL
            email_subject: Email subject
            email_date: Email date
        """
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
                    # Wait for MR with timeout to allow checking running flag
                    try:
                        mr_info = await asyncio.wait_for(self.mr_queue.get(), timeout=1.0)
                    except asyncio.TimeoutError:
                        continue
                    
                    logger.info(f"Processing MR from queue: {mr_info['url']}")
                    
                    # Process the MR
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
                    
                except Exception as e:
                    logger.error(f"Error processing MR queue: {e}", exc_info=True)
        except asyncio.CancelledError:
            logger.info("MR queue processor stopped")
            raise
    
    async def start(self):
        """Start the service."""
        logger.info("=" * 60)
        logger.info("GitLab MR Summarizer Service Starting...")
        logger.info("=" * 60)
        
        # Create async resources
        self.mr_queue = asyncio.Queue()
        self.shutdown_event = asyncio.Event()
        
        # Setup signal handlers
        loop = asyncio.get_running_loop()
        
        def signal_handler():
            logger.info("Received shutdown signal")
            self.running = False
            logger.info("Setting shutdown event...")
            self.shutdown_event.set()
        
        try:
            loop.add_signal_handler(signal.SIGTERM, signal_handler)
            loop.add_signal_handler(signal.SIGINT, signal_handler)
            logger.info("Signal handlers registered")
        except Exception as e:
            logger.error(f"Failed to register signal handlers: {e}")
        
        # Validate configuration
        errors = self.config.validate()
        if errors:
            logger.error("Configuration errors:")
            for error in errors:
                logger.error(f"  - {error}")
            logger.error("Please fix configuration and restart.")
            return
        
        logger.info(f"GitLab URL: {self.config.gitlab_url}")
        logger.info(f"Email: {self.config.gmail_email}")
        logger.info(f"Ollama Model: {self.config.ollama_model}")
        logger.info(f"Check Interval: {self.config.check_interval}s")
        logger.info("=" * 60)
        
        self.running = True
        
        try:
            # Start orchestrator
            await self.orchestrator.start()
            
            # Start background tasks
            email_task = asyncio.create_task(self.email_monitor.start_monitoring())
            queue_task = asyncio.create_task(self.process_queue())
            
            # Store tasks for cleanup
            self.tasks = [email_task, queue_task]
            
            logger.info("✅ Service started successfully!")
            logger.info("Monitoring for GitLab assignment notifications...")
            logger.info("Press Ctrl+C to stop.")
            
            # Wait for shutdown signal
            logger.info("Waiting for shutdown signal...")
            await self.shutdown_event.wait()
            logger.info("Shutdown signal received, proceeding with shutdown...")
            
            # Cancel tasks
            logger.info("Cancelling background tasks...")
            for task in self.tasks:
                if not task.done():
                    task.cancel()
            
            # Wait for tasks to finish cancelling
            await asyncio.gather(*self.tasks, return_exceptions=True)
            logger.info("Background tasks stopped")
            
        except asyncio.CancelledError:
            logger.info("Service cancelled")
        except Exception as e:
            logger.error(f"Error in service: {e}", exc_info=True)
        finally:
            await self.stop()
    
    async def stop(self):
        """Stop the service."""
        logger.info("Stopping service...")
        self.running = False
        
        # Stop orchestrator
        await self.orchestrator.stop()
        
        logger.info("Service stopped.")


async def main():
    """Main entry point."""
    # Load configuration
    config = Config.from_env()
    
    # Create service
    service = GitLabMRSummarizer(config)
    
    # Start service
    try:
        await service.start()
    except asyncio.CancelledError:
        logger.info("Service cancelled")
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt")
    finally:
        logger.info("Cleanup complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

