"""Configuration management."""
import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv


@dataclass
class Config:
    """Application configuration."""
    
    # GitLab
    gitlab_url: str
    gitlab_token: str
    # the gitlab email from which is coming the MR requests
    gitlab_from_email: str
    
    # Gmail
    gmail_email: str
    gmail_app_password: str
    
    # Ollama
    ollama_base_url: str
    ollama_model: str
    
    # Service URLs (for client)
    gitlab_server_url: str
    llm_server_url: str
    
    # Redis
    redis_url: str
    use_redis: bool
    
    # Monitoring
    check_interval: int
    log_level: str
    
    # MR Processing
    mr_states_to_process: list[str]
    
    # LLM Prompt Limits
    max_files_in_prompt: int
    max_diff_lines_per_file: int
    
    # Database
    processed_emails_db: str
    
    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        # Try to load from .env file in project root
        env_path = Path(__file__).parent.parent.parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)
        else:
            load_dotenv()  # Try to load from current directory
        
        # Parse MR states to process
        mr_states_str = os.getenv("MR_STATES_TO_PROCESS", "opened")
        mr_states = [state.strip().lower() for state in mr_states_str.split(",")]
        
        return cls(
            gitlab_url=os.getenv("GITLAB_URL", "https://gitlab.com"),
            gitlab_token=os.getenv("GITLAB_TOKEN", ""),
            gmail_email=os.getenv("GMAIL_EMAIL", ""),
            gitlab_from_email=os.getenv("GITLAB_FROM_EMAIL", "gitlab@mg.gitlab.com"),
            gmail_app_password=os.getenv("GMAIL_APP_PASSWORD", ""),
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            ollama_model=os.getenv("OLLAMA_MODEL", "codellama"),
            check_interval=int(os.getenv("CHECK_INTERVAL", "60")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            mr_states_to_process=mr_states,
            max_files_in_prompt=int(os.getenv("MAX_FILES_IN_PROMPT", "999999")),  # No limit by default
            max_diff_lines_per_file=int(os.getenv("MAX_DIFF_LINES_PER_FILE", "999999")),  # No limit by default
            processed_emails_db=os.getenv("PROCESSED_EMAILS_DB", ".processed_emails.json"),
            gitlab_server_url=os.getenv("GITLAB_SERVER_URL", "http://localhost:8001"),
            llm_server_url=os.getenv("LLM_SERVER_URL", "http://localhost:8002"),
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            use_redis=os.getenv("USE_REDIS", "false").lower() in ("true", "1", "yes"),
        )
    
    def validate(self) -> list[str]:
        """Validate configuration and return list of errors."""
        errors = []
        
        if not self.gitlab_token:
            errors.append("GITLAB_TOKEN is required")
        
        if not self.gmail_email:
            errors.append("GMAIL_EMAIL is required")
        
        if not self.gmail_app_password:
            errors.append("GMAIL_APP_PASSWORD is required")
        
        if self.check_interval <= 0:
            errors.append("CHECK_INTERVAL must be positive")
        
        return errors

