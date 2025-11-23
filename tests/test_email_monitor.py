"""Tests for email monitoring functionality."""

import pytest
import email
from email import policy
from pathlib import Path
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.client.email_monitor import EmailMonitor
from src.utils.config import Config


@pytest.fixture
def test_config():
    """Create a test configuration."""
    return Config(
        gitlab_url="https://gitlab.com",
        gitlab_token="fake-token",
        gmail_email="test@example.com",
        gmail_app_password="fake-password",
        check_interval=60,
        ollama_base_url="http://localhost:11434",
        ollama_model="codellama",
        log_level="INFO",
        mr_states_to_process=["opened"],
        processed_emails_db=".test_processed_emails.json"
    )


@pytest.fixture
def test_monitor(test_config):
    """Create a test email monitor with a dummy callback."""
    async def dummy_callback(mr_url: str):
        """Dummy callback for testing."""
        pass
    
    return EmailMonitor(test_config, dummy_callback)


class TestURLExtraction:
    """Test GitLab MR URL extraction from emails."""
    
    def test_extract_url_from_plain_text(self, test_monitor):
        """Test URL extraction from plain text."""
        monitor = test_monitor
        
        body = """
        Razvan Tudorica was added as an assignee.
        
        —
        Reply to this email directly or view it on GitLab
        <https://gitlab.com/picsart/ai-engineering/b2b/image-processing-service/-/merge_requests/24>
        .
        """
        
        url = monitor._extract_gitlab_mr_url(body)
        assert url == "https://gitlab.com/picsart/ai-engineering/b2b/image-processing-service/-/merge_requests/24"
    
    def test_extract_url_without_brackets(self, test_monitor):
        """Test URL extraction without angle brackets."""
        monitor = test_monitor
        
        body = """
        Check out this MR: https://gitlab.com/group/project/-/merge_requests/42
        """
        
        url = monitor._extract_gitlab_mr_url(body)
        assert url == "https://gitlab.com/group/project/-/merge_requests/42"
    
    def test_extract_url_with_http(self, test_monitor):
        """Test URL extraction with http (not https)."""
        monitor = test_monitor
        
        body = """
        http://gitlab.example.com/team/repo/-/merge_requests/123
        """
        
        url = monitor._extract_gitlab_mr_url(body)
        assert url == "http://gitlab.example.com/team/repo/-/merge_requests/123"
    
    def test_extract_url_deep_hierarchy(self, test_monitor):
        """Test URL extraction with deep project hierarchy."""
        monitor = test_monitor
        
        body = """
        https://gitlab.com/a/b/c/d/e/f/-/merge_requests/999
        """
        
        url = monitor._extract_gitlab_mr_url(body)
        assert url == "https://gitlab.com/a/b/c/d/e/f/-/merge_requests/999"
    
    def test_no_url_found(self, test_monitor):
        """Test when no URL is present."""
        monitor = test_monitor
        
        body = """
        This is just a regular email with no MR URL.
        """
        
        url = monitor._extract_gitlab_mr_url(body)
        assert url is None
    
    def test_extract_url_from_real_email(self, test_monitor):
        """Test URL extraction from actual email file."""
        email_path = Path(__file__).parent.parent / "logs" / "test cicd3 (1).eml"
        
        if not email_path.exists():
            pytest.skip(f"Email file not found: {email_path}")
        
        # Read the email file
        with open(email_path, 'rb') as f:
            email_message = email.message_from_bytes(f.read(), policy=policy.default)
        
        # Extract body text (same logic as email_monitor.py)
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
        
        monitor = test_monitor
        
        url = monitor._extract_gitlab_mr_url(body_text)
        assert url == "https://gitlab.com/picsart/ai-engineering/b2b/image-processing-service/-/merge_requests/24"


class TestAssignmentDetection:
    """Test GitLab assignment email detection."""
    
    def test_detect_assignment_email(self, test_monitor):
        """Test detection of assignment notification."""
        monitor = test_monitor
        
        subject = "MR Assignment"
        body = "John Doe was added as an assignee."
        
        is_assignment = monitor._is_gitlab_assignment_email(subject, body)
        assert is_assignment is True
    
    def test_detect_assignment_email_variant2(self, test_monitor):
        """Test detection with different wording."""
        monitor = test_monitor
        
        subject = "You have been assigned"
        body = "GitLab assigned you to merge request #42"
        
        is_assignment = monitor._is_gitlab_assignment_email(subject, body)
        assert is_assignment is True
    
    def test_detect_non_assignment_email(self, test_monitor):
        """Test that non-assignment emails are not detected."""
        monitor = test_monitor
        
        subject = "Random email"
        body = "This is just a random email about something else."
        
        is_assignment = monitor._is_gitlab_assignment_email(subject, body)
        assert is_assignment is False

