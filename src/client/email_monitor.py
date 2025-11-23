"""Email monitor for GitLab assignment notifications."""
import asyncio
import imaplib
import email
import json
import logging
import re
from email.header import decode_header
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Optional, Set
from datetime import datetime, timezone

from ..utils.config import Config

logger = logging.getLogger(__name__)


class EmailMonitor:
    """Monitor Gmail for GitLab assignment notifications."""
    
    def __init__(self, config: Config, on_mr_detected: callable):
        """Initialize email monitor.
        
        Args:
            config: Application configuration
            on_mr_detected: Callback function(mr_url, email_subject, email_date)
        """
        self.config = config
        self.on_mr_detected = on_mr_detected
        self.processed_emails_file = Path(config.processed_emails_db)
        self.processed_emails: Set[str] = self._load_processed_emails()
        
        # Store start time - only process emails newer than this
        self.start_time = datetime.now(timezone.utc)
        logger.info(f"Email monitor initialized - will only process emails after {self.start_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    def _load_processed_emails(self) -> Set[str]:
        """Load set of processed email IDs from file."""
        if self.processed_emails_file.exists():
            try:
                with open(self.processed_emails_file, 'r') as f:
                    data = json.load(f)
                    return set(data.get("processed_ids", []))
            except Exception as e:
                logger.error(f"Error loading processed emails: {e}")
                return set()
        return set()
    
    def _save_processed_emails(self):
        """Save processed email IDs to file."""
        try:
            with open(self.processed_emails_file, 'w') as f:
                json.dump({
                    "processed_ids": list(self.processed_emails),
                    "last_updated": datetime.now().isoformat(),
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving processed emails: {e}")
    
    def _decode_header_value(self, header_value: str) -> str:
        """Decode email header value.
        
        Args:
            header_value: Raw header value
            
        Returns:
            Decoded string
        """
        decoded_parts = decode_header(header_value)
        decoded_string = ""
        
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                decoded_string += part.decode(encoding or 'utf-8', errors='ignore')
            else:
                decoded_string += part
        
        return decoded_string
    
    def _parse_email_date(self, date_str: str) -> Optional[datetime]:
        """Parse email date string to datetime.
        
        Args:
            date_str: Email date header value
            
        Returns:
            datetime object or None if parsing fails
        """
        try:
            return parsedate_to_datetime(date_str)
        except Exception as e:
            logger.warning(f"Failed to parse email date '{date_str}': {e}")
            return None
    
    def _extract_gitlab_mr_url(self, email_body: str) -> Optional[str]:
        """Extract GitLab MR URL from email body.
        
        Args:
            email_body: Email body text
            
        Returns:
            GitLab MR URL or None
        """
        # Look for patterns like:
        # https://gitlab.com/group/project/-/merge_requests/123
        # or view it on GitLab with link
        # Also handle URLs in angle brackets like <https://...>
        # Use .+? for path to handle any depth of project hierarchy
        patterns = [
            r'https?://[^\s<>]+/-/merge_requests/\d+',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, email_body)
            if match:
                url = match.group(0)
                # Clean up any trailing characters
                url = url.rstrip('>').rstrip('.')
                logger.info(f"Extracted URL: {url}")
                return url
        
        logger.warning(f"No URL matched in body (first 500 chars): {email_body[:500]}")
        return None
    
    def _is_gitlab_assignment_email(self, subject: str, body: str) -> bool:
        """Check if email is a GitLab assignment notification.
        
        Args:
            subject: Email subject
            body: Email body
            
        Returns:
            True if this is an assignment notification
        """
        # Check for assignment indicators
        assignment_indicators = [
            "was added as an assignee",
            "assigned you to merge request",
            "assigned merge request",
        ]
        
        text_to_check = (subject + " " + body).lower()
        
        for indicator in assignment_indicators:
            if indicator in text_to_check:
                return True
        
        return False
    
    async def check_emails(self):
        """Check for new GitLab assignment emails."""
        try:
            # Connect to Gmail IMAP
            mail = imaplib.IMAP4_SSL("imap.gmail.com")
            mail.login(self.config.gmail_email, self.config.gmail_app_password)
            mail.select("inbox")
            
            # Search for GitLab emails since start time (IMAP server-side filtering)
            since_date = self.start_time.strftime("%d-%b-%Y")
            # search_criteria = f'(FROM "gitlab" SINCE {since_date})'
            search_criteria = f'(FROM "razvantudorica@gmail.com" SINCE {since_date})'
            logger.info(f"Searching with criteria: {search_criteria}")
            _, message_numbers = mail.search(None, search_criteria)
            
            email_ids = message_numbers[0].split()
            logger.info(f"Found {len(email_ids)} GitLab emails since {since_date}")
            
            new_assignments = 0
            
            for email_id in email_ids[-50:]:  # Check last 50 emails
                email_id_str = email_id.decode()
                
                # Skip if already processed
                if email_id_str in self.processed_emails:
                    logger.debug(f"Skipping already processed email ID: {email_id_str}")
                    continue
                
                # Fetch email
                _, msg_data = mail.fetch(email_id, "(RFC822)")
                email_body = msg_data[0][1]
                email_message = email.message_from_bytes(email_body)
                
                # Get subject
                subject = self._decode_header_value(email_message.get("Subject", ""))
                logger.info(f"Checking email: {subject}")
                
                # Get email date
                email_date = email_message.get("Date", "")
                
                # Double-check email date (client-side filtering as backup)
                email_datetime = self._parse_email_date(email_date)
                if email_datetime:
                    # Make timezone-aware if it isn't already
                    if email_datetime.tzinfo is None:
                        email_datetime = email_datetime.replace(tzinfo=timezone.utc)
                    
                    if email_datetime < self.start_time:
                        logger.info(f"⏭️  Skipping old email: {subject} (received {email_datetime}, before start {self.start_time})")
                        # Mark as processed to avoid checking again
                        self.processed_emails.add(email_id_str)
                        continue
                
                # Get body
                body_text = ""
                if email_message.is_multipart():
                    for part in email_message.walk():
                        if part.get_content_type() == "text/plain":
                            try:
                                body_text += part.get_payload(decode=True).decode('utf-8', errors='ignore')
                            except:
                                pass
                        elif part.get_content_type() == "text/html":
                            try:
                                body_text += part.get_payload(decode=True).decode('utf-8', errors='ignore')
                            except:
                                pass
                else:
                    try:
                        body_text = email_message.get_payload(decode=True).decode('utf-8', errors='ignore')
                    except:
                        body_text = str(email_message.get_payload())
                
                # Check if this is an assignment email
                if self._is_gitlab_assignment_email(subject, body_text):
                    # Extract MR URL
                    logger.info(f"Email body excerpt: {body_text[:300]}")
                    mr_url = self._extract_gitlab_mr_url(body_text)
                    
                    if mr_url:
                        logger.info(f"Found GitLab assignment: {subject}")
                        logger.info(f"MR URL: {mr_url}")
                        
                        # Mark as processed
                        self.processed_emails.add(email_id_str)
                        self._save_processed_emails()
                        
                        # Trigger callback
                        await self.on_mr_detected(mr_url, subject, email_date)
                        new_assignments += 1
                    else:
                        logger.warning(f"Assignment email but no MR URL found: {subject}")
                        # Mark as processed anyway to avoid reprocessing
                        self.processed_emails.add(email_id_str)
                        self._save_processed_emails()
                else:
                    # Mark as processed (not an assignment)
                    logger.info(f"ℹ️  Not an assignment email: {subject}")
                    self.processed_emails.add(email_id_str)
            
            if new_assignments > 0:
                self._save_processed_emails()
                logger.info(f"Processed {new_assignments} new assignment(s)")
            
            mail.close()
            mail.logout()
            
        except imaplib.IMAP4.error as e:
            logger.error(f"IMAP error: {e}")
        except Exception as e:
            logger.error(f"Error checking emails: {e}", exc_info=True)
    
    async def start_monitoring(self):
        """Start monitoring emails in a loop."""
        logger.info(f"Starting email monitoring (checking every {self.config.check_interval}s)")
        
        try:
            while True:
                try:
                    await self.check_emails()
                except Exception as e:
                    logger.error(f"Error in monitoring loop: {e}", exc_info=True)
                
                # Wait before next check (with periodic checks for cancellation)
                for _ in range(self.config.check_interval):
                    await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("Email monitoring stopped")
            raise


async def test_monitor():
    """Test email monitor."""
    from ..utils.config import Config
    
    config = Config.from_env()
    
    async def on_mr_detected(mr_url: str, subject: str, date: str):
        print(f"\n=== MR Detected ===")
        print(f"Subject: {subject}")
        print(f"Date: {date}")
        print(f"URL: {mr_url}")
        print(f"==================\n")
    
    monitor = EmailMonitor(config, on_mr_detected)
    
    # Run one check
    await monitor.check_emails()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_monitor())

