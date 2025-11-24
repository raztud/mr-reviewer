"""Email monitor for GitLab assignment notifications."""
import asyncio
import imaplib
import email
import logging
import re
from email.header import decode_header
from email.utils import parsedate_to_datetime
from typing import Optional
from datetime import datetime, timezone, timedelta

from src.utils.config import Config
from src.utils.email_storage import create_email_storage, EmailStorage

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
        
        # Use storage factory to get appropriate backend (Redis or JSON)
        self.storage: EmailStorage = create_email_storage(config)
        
        # Store start time for reference
        self.start_time = datetime.now(timezone.utc)
        logger.info(f"Email monitor initialized - will process emails from last 24 hours")
    
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
            "was added as a reviewer",
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
            
            # Search for GitLab emails from last 24 hours (IMAP server-side filtering)
            twenty_four_hours_ago = datetime.now(timezone.utc) - timedelta(hours=24)
            since_date = twenty_four_hours_ago.strftime("%d-%b-%Y")
            search_criteria = f'(FROM "{self.config.gitlab_from_email}" SINCE {since_date})'
            logger.info(f"Searching with criteria: {search_criteria} (last 24 hours)")
            _, message_numbers = mail.search(None, search_criteria)
            
            email_ids = message_numbers[0].split()
            logger.info(f"Found {len(email_ids)} GitLab emails since {since_date}")
            
            new_assignments = 0
            
            for email_id in email_ids[-50:]:  # Check last 50 emails
                email_id_str = email_id.decode()
                
                # Skip if already processed
                if self.storage.contains(email_id_str):
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
                
                # Double-check email date (client-side filtering - only process last 24 hours)
                email_datetime = self._parse_email_date(email_date)
                if email_datetime:
                    # Make timezone-aware if it isn't already
                    if email_datetime.tzinfo is None:
                        email_datetime = email_datetime.replace(tzinfo=timezone.utc)
                    
                    # Calculate 24 hour cutoff
                    twenty_four_hours_ago = datetime.now(timezone.utc) - timedelta(hours=24)
                    
                    if email_datetime < twenty_four_hours_ago:
                        logger.info(f"⏭️  Skipping old email: {subject} (received {email_datetime}, older than 24 hours)")
                        # Mark as processed to avoid checking again
                        self.storage.add(email_id_str)
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
                        self.storage.add(email_id_str)
                        self.storage.save()  # Explicit save for compatibility
                        
                        # Trigger callback
                        await self.on_mr_detected(mr_url, subject, email_date)
                        new_assignments += 1
                    else:
                        logger.warning(f"Assignment email but no MR URL found: {subject}")
                        # Mark as processed anyway to avoid reprocessing
                        self.storage.add(email_id_str)
                        self.storage.save()
                else:
                    # Mark as processed (not an assignment)
                    logger.info(f"ℹ️  Not an assignment email: {subject}, email id: {email_id_str}")
                    self.storage.add(email_id_str)
            
            if new_assignments > 0:
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
