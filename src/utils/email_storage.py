"""Storage backend for tracking processed emails."""
import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Set
from datetime import datetime

logger = logging.getLogger(__name__)


class EmailStorage(ABC):
    """Abstract base class for email storage."""
    
    @abstractmethod
    def add(self, email_id: str) -> None:
        """Add an email ID to the processed set."""
        pass
    
    @abstractmethod
    def contains(self, email_id: str) -> bool:
        """Check if an email ID has been processed."""
        pass
    
    @abstractmethod
    def get_all(self) -> Set[str]:
        """Get all processed email IDs."""
        pass
    
    @abstractmethod
    def save(self) -> None:
        """Persist the storage (if needed)."""
        pass
    
    @abstractmethod
    def load(self) -> None:
        """Load from persistent storage (if needed)."""
        pass


class JSONEmailStorage(EmailStorage):
    """JSON file-based email storage (original implementation)."""
    
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.processed_emails: Set[str] = set()
        self.load()
    
    def add(self, email_id: str) -> None:
        """Add an email ID to the processed set."""
        self.processed_emails.add(email_id)
    
    def contains(self, email_id: str) -> bool:
        """Check if an email ID has been processed."""
        return email_id in self.processed_emails
    
    def get_all(self) -> Set[str]:
        """Get all processed email IDs."""
        return self.processed_emails.copy()
    
    def save(self) -> None:
        """Save processed emails to JSON file."""
        try:
            data = {
                "processed_ids": list(self.processed_emails),
                "last_updated": datetime.now().isoformat()
            }
            with open(self.db_path, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Saved {len(self.processed_emails)} processed emails to {self.db_path}")
        except Exception as e:
            logger.error(f"Error saving processed emails: {e}")
    
    def load(self) -> None:
        """Load processed emails from JSON file."""
        if not self.db_path.exists():
            logger.info(f"No existing processed emails database at {self.db_path}")
            self.processed_emails = set()
            return
        
        try:
            with open(self.db_path, 'r') as f:
                data = json.load(f)
                self.processed_emails = set(data.get("processed_ids", []))
            logger.info(f"Loaded {len(self.processed_emails)} processed emails from {self.db_path}")
        except Exception as e:
            logger.error(f"Error loading processed emails: {e}")
            self.processed_emails = set()


class RedisEmailStorage(EmailStorage):
    """Redis-based email storage with persistence."""
    
    def __init__(self, redis_url: str, key_prefix: str = "gitlab_mr_summarizer"):
        try:
            import redis
            self.redis = redis.from_url(redis_url, decode_responses=True)
            self.key = f"{key_prefix}:processed_emails"
            self._test_connection()
            logger.info(f"Connected to Redis at {redis_url}")
        except ImportError:
            raise ImportError("redis package not installed. Run: pip install redis")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    def _test_connection(self) -> None:
        """Test Redis connection."""
        try:
            self.redis.ping()
        except Exception as e:
            raise ConnectionError(f"Cannot connect to Redis: {e}")
    
    def add(self, email_id: str) -> None:
        """Add an email ID to the processed set in Redis."""
        try:
            self.redis.sadd(self.key, email_id)
            logger.debug(f"Added email ID {email_id} to Redis")
        except Exception as e:
            logger.error(f"Error adding email to Redis: {e}")
            raise
    
    def contains(self, email_id: str) -> bool:
        """Check if an email ID has been processed."""
        try:
            return self.redis.sismember(self.key, email_id)
        except Exception as e:
            logger.error(f"Error checking email in Redis: {e}")
            raise
    
    def get_all(self) -> Set[str]:
        """Get all processed email IDs from Redis."""
        try:
            return self.redis.smembers(self.key)
        except Exception as e:
            logger.error(f"Error getting all emails from Redis: {e}")
            raise
    
    def save(self) -> None:
        """Redis automatically persists data (no-op for compatibility)."""
        pass
    
    def load(self) -> None:
        """Redis automatically loads data (no-op for compatibility)."""
        pass
    
    def count(self) -> int:
        """Get count of processed emails."""
        try:
            return self.redis.scard(self.key)
        except Exception as e:
            logger.error(f"Error counting emails in Redis: {e}")
            return 0


def create_email_storage(config) -> EmailStorage:
    """Factory function to create the appropriate storage backend.
    
    Args:
        config: Config object with redis_url, use_redis, and processed_emails_db
        
    Returns:
        EmailStorage instance (Redis or JSON based on config)
    """
    if config.use_redis:
        logger.info("Using Redis for email storage")
        try:
            return RedisEmailStorage(config.redis_url)
        except Exception as e:
            logger.warning(f"Failed to initialize Redis storage: {e}")
            logger.warning("Falling back to JSON storage")
            return JSONEmailStorage(config.processed_emails_db)
    else:
        logger.info("Using JSON file for email storage")
        return JSONEmailStorage(config.processed_emails_db)

