import re
import time
import hashlib
import secrets
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

class RateLimiter:
    """Rate limiter for API endpoints and commands."""
    
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, List[float]] = defaultdict(list)
    
    def is_allowed(self, identifier: str) -> Tuple[bool, float]:
        """
        Check if request is allowed.
        
        Returns:
            (is_allowed, retry_after_seconds)
        """
        now = time.time()
        user_requests = self.requests[identifier]
        
        # Remove old requests outside the window
        user_requests[:] = [req_time for req_time in user_requests 
                          if now - req_time < self.window_seconds]
        
        if len(user_requests) >= self.max_requests:
            retry_after = self.window_seconds - (now - user_requests[0])
            return False, max(0, retry_after)
        
        user_requests.append(now)
        return True, 0

class InputValidator:
    """Input validation utilities."""
    
    @staticmethod
    def validate_discord_id(discord_id: str) -> bool:
        """Validate Discord user ID format."""
        if not discord_id:
            return False
        return bool(re.match(r'^\d{17,19}$', discord_id))
    
    @staticmethod
    def validate_github_username(username: str) -> bool:
        """Validate GitHub username format."""
        if not username:
            return False
        # GitHub usernames: 1-39 characters, alphanumeric and hyphens, no consecutive hyphens
        return bool(re.match(r'^[a-zA-Z0-9](?:[a-zA-Z0-9]|-(?=[a-zA-Z0-9])){0,38}$', username))
    
    @staticmethod
    def validate_hours(hours: float) -> bool:
        """Validate volunteer hours."""
        return isinstance(hours, (int, float)) and 0 < hours <= 24
    
    @staticmethod
    def validate_limit(limit: int) -> bool:
        """Validate pagination limit."""
        return isinstance(limit, int) and 1 <= limit <= 100
    
    @staticmethod
    def validate_commit_sha(commit_sha: str) -> bool:
        """Validate Git commit SHA format."""
        if not commit_sha:
            return False
        return bool(re.match(r'^[a-fA-F0-9]{7,40}$', commit_sha))
    
    @staticmethod
    def sanitize_string(text: str, max_length: int = 1000) -> str:
        """Sanitize user input string."""
        if not text:
            return ""
        # Remove null bytes and control characters
        sanitized = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
        # Limit length
        return sanitized[:max_length]

class SecurityUtils:
    """Security utility functions."""
    
    @staticmethod
    def generate_secure_state() -> str:
        """Generate cryptographically secure state token."""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def hash_sensitive_data(data: str) -> str:
        """Hash sensitive data for logging."""
        return hashlib.sha256(data.encode()).hexdigest()[:8]
    
    @staticmethod
    def mask_token(token: str) -> str:
        """Mask token for safe logging."""
        if not token or len(token) < 8:
            return "***"
        return f"{token[:4]}...{token[-4:]}"
    
    @staticmethod
    def validate_oauth_state(state: str) -> bool:
        """Validate OAuth state token format."""
        if not state:
            return False
        # State should be base64 URL safe and reasonable length
        return bool(re.match(r'^[A-Za-z0-9_-]{20,}$', state))

class DatabaseSecurity:
    """Database security utilities."""
    
    @staticmethod
    def get_secure_connection_string(db_path: str) -> str:
        """Get secure database connection string."""
        # For SQLite, add timeout and other security options
        return f"file:{db_path}?timeout=30&mode=rwc"
    
    @staticmethod
    def validate_sql_identifier(identifier: str) -> bool:
        """Validate SQL identifier to prevent injection."""
        if not identifier:
            return False
        # Only allow alphanumeric, underscore, and dot
        return bool(re.match(r'^[a-zA-Z_][a-zA-Z0-9_.]*$', identifier))

# Global rate limiters
oauth_rate_limiter = RateLimiter(max_requests=5, window_seconds=300)  # 5 requests per 5 minutes
bot_command_rate_limiter = RateLimiter(max_requests=10, window_seconds=60)  # 10 commands per minute 