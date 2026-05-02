"""validation.py

Input validation for DriftGuard CLI and API with user-friendly error messages.
"""
import os
import re
from pathlib import Path
from typing import Tuple, Optional
from urllib.parse import urlparse


class ValidationError(Exception):
    """Custom validation error with structured information."""
    
    def __init__(self, message: str, hint: str = "", code: str = "VALIDATION_ERROR"):
        """Initialize validation error.
        
        Args:
            message: Error message describing what failed
            hint: Actionable hint on how to fix the issue
            code: Error code for programmatic handling
        """
        self.message = message
        self.hint = hint
        self.code = code
        super().__init__(message)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "error": self.message,
            "hint": self.hint,
            "code": self.code
        }


def validate_repo_path(repo: str, github_token: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """Validate repository input (local path or remote URL).
    
    Args:
        repo: Repository path or URL
        github_token: Optional GitHub token for private repos
        
    Returns:
        Tuple of (is_valid, error_message)
        
    Raises:
        ValidationError: If validation fails with actionable error message
    """
    # Check if it's a URL
    if repo.startswith(('http://', 'https://', 'git@')):
        return _validate_remote_repo(repo, github_token)
    
    # Validate local path
    return _validate_local_repo(repo)


def _validate_local_repo(repo: str) -> Tuple[bool, Optional[str]]:
    """Validate local repository path.
    
    Args:
        repo: Local path to repository
        
    Returns:
        Tuple of (is_valid, error_message)
        
    Raises:
        ValidationError: If validation fails
    """
    repo_path = Path(repo).resolve()
    
    # Check if path exists
    if not repo_path.exists():
        raise ValidationError(
            message=f"Repository path does not exist: {repo}",
            hint=f"Ensure the path exists or use '.' for current directory. Resolved path: {repo_path}",
            code="REPO_NOT_FOUND"
        )
    
    # Check if it's a directory
    if not repo_path.is_dir():
        raise ValidationError(
            message=f"Repository path is not a directory: {repo}",
            hint="Provide a path to a directory containing a git repository",
            code="REPO_NOT_DIRECTORY"
        )
    
    # Check if it's a git repository
    git_dir = repo_path / ".git"
    if not git_dir.exists():
        raise ValidationError(
            message=f"Not a git repository: {repo}",
            hint="Initialize git repository with 'git init' or provide a valid git repository path",
            code="NOT_GIT_REPO"
        )
    
    return True, None


def _validate_remote_repo(repo: str, github_token: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """Validate remote repository URL.
    
    Args:
        repo: Remote repository URL
        github_token: Optional GitHub token
        
    Returns:
        Tuple of (is_valid, error_message)
        
    Raises:
        ValidationError: If validation fails
    """
    # Parse GitHub URLs
    github_patterns = [
        r'https://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$',
        r'git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$',
    ]
    
    for pattern in github_patterns:
        match = re.match(pattern, repo)
        if match:
            owner, repo_name = match.groups()
            # Basic validation - actual API check happens in git_parser
            if not owner or not repo_name:
                raise ValidationError(
                    message=f"Invalid GitHub URL format: {repo}",
                    hint="Use format: https://github.com/owner/repo or git@github.com:owner/repo",
                    code="INVALID_GITHUB_URL"
                )
            return True, None
    
    # Generic URL validation
    try:
        parsed = urlparse(repo)
        if not parsed.scheme or not parsed.netloc:
            raise ValidationError(
                message=f"Invalid repository URL: {repo}",
                hint="Provide a valid URL (e.g., https://github.com/owner/repo) or local path",
                code="INVALID_URL"
            )
    except Exception as e:
        raise ValidationError(
            message=f"Invalid repository URL: {repo}",
            hint=f"Provide a valid URL or local path. Error: {str(e)}",
            code="INVALID_URL"
        )
    
    return True, None


def validate_days(days: int) -> Tuple[bool, Optional[str]]:
    """Validate days parameter.
    
    Args:
        days: Number of days to analyze
        
    Returns:
        Tuple of (is_valid, error_message)
        
    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(days, int):
        raise ValidationError(
            message=f"Days must be an integer, got: {type(days).__name__}",
            hint="Provide a positive integer for days (e.g., --days 30)",
            code="INVALID_DAYS_TYPE"
        )
    
    if days <= 0:
        raise ValidationError(
            message=f"Days must be positive, got: {days}",
            hint="Provide a positive number of days (e.g., --days 30)",
            code="INVALID_DAYS_VALUE"
        )
    
    if days > 365:
        raise ValidationError(
            message=f"Days cannot exceed 365, got: {days}",
            hint="Analyzing more than 1 year of history may be slow. Use --days 365 or less",
            code="DAYS_TOO_LARGE"
        )
    
    return True, None


def validate_max_files(max_files: int) -> Tuple[bool, Optional[str]]:
    """Validate max_files parameter.
    
    Args:
        max_files: Maximum number of files to analyze
        
    Returns:
        Tuple of (is_valid, error_message)
        
    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(max_files, int):
        raise ValidationError(
            message=f"Max files must be an integer, got: {type(max_files).__name__}",
            hint="Provide a positive integer for max-files (e.g., --max-files 20)",
            code="INVALID_MAX_FILES_TYPE"
        )
    
    if max_files <= 0:
        raise ValidationError(
            message=f"Max files must be positive, got: {max_files}",
            hint="Provide a positive number of files (e.g., --max-files 20)",
            code="INVALID_MAX_FILES_VALUE"
        )
    
    if max_files > 100:
        raise ValidationError(
            message=f"Max files cannot exceed 100, got: {max_files}",
            hint="Analyzing more than 100 files may be slow. Use --max-files 100 or less",
            code="MAX_FILES_TOO_LARGE"
        )
    
    return True, None


def validate_interval(interval_str: str) -> Tuple[bool, Optional[str]]:
    """Validate interval string format.
    
    Args:
        interval_str: Interval string (e.g., "24h", "30m", "3600")
        
    Returns:
        Tuple of (is_valid, error_message)
        
    Raises:
        ValidationError: If validation fails
    """
    # Try plain number first
    try:
        seconds = int(interval_str)
        if seconds <= 0:
            raise ValidationError(
                message=f"Interval must be positive, got: {seconds} seconds",
                hint="Provide a positive interval (e.g., --interval 24h or --interval 3600)",
                code="INVALID_INTERVAL_VALUE"
            )
        if seconds < 60:
            raise ValidationError(
                message=f"Interval too short: {seconds} seconds",
                hint="Minimum interval is 60 seconds (1 minute). Use --interval 1m or higher",
                code="INTERVAL_TOO_SHORT"
            )
        return True, None
    except ValueError:
        pass
    
    # Parse with unit suffix
    match = re.match(r'^(\d+)([hms])$', interval_str.lower())
    if not match:
        raise ValidationError(
            message=f"Invalid interval format: {interval_str}",
            hint="Use format like '24h' (hours), '30m' (minutes), '3600s' (seconds), or plain seconds",
            code="INVALID_INTERVAL_FORMAT"
        )
    
    value, unit = match.groups()
    value = int(value)
    
    if value <= 0:
        raise ValidationError(
            message=f"Interval value must be positive, got: {value}{unit}",
            hint="Provide a positive interval (e.g., --interval 24h)",
            code="INVALID_INTERVAL_VALUE"
        )
    
    # Convert to seconds for validation
    seconds = 0
    if unit == 'h':
        seconds = value * 3600
    elif unit == 'm':
        seconds = value * 60
    elif unit == 's':
        seconds = value
    
    if seconds < 60:
        raise ValidationError(
            message=f"Interval too short: {interval_str} ({seconds} seconds)",
            hint="Minimum interval is 60 seconds (1 minute). Use --interval 1m or higher",
            code="INTERVAL_TOO_SHORT"
        )
    
    return True, None


def validate_export_mode(export_mode: str) -> Tuple[bool, Optional[str]]:
    """Validate export mode parameter.
    
    Args:
        export_mode: Export format (json, markdown, pdf, all)
        
    Returns:
        Tuple of (is_valid, error_message)
        
    Raises:
        ValidationError: If validation fails
    """
    valid_modes = ["json", "markdown", "pdf", "all"]
    
    if export_mode not in valid_modes:
        raise ValidationError(
            message=f"Invalid export mode: {export_mode}",
            hint=f"Use one of: {', '.join(valid_modes)}",
            code="INVALID_EXPORT_MODE"
        )
    
    return True, None


def validate_file_path(file_path: str) -> Tuple[bool, Optional[str]]:
    """Validate file path for API queries.
    
    Args:
        file_path: File path to validate
        
    Returns:
        Tuple of (is_valid, error_message)
        
    Raises:
        ValidationError: If validation fails
    """
    if not file_path:
        raise ValidationError(
            message="File path cannot be empty",
            hint="Provide a valid file path (e.g., app/main.py)",
            code="EMPTY_FILE_PATH"
        )
    
    if file_path.startswith('/') or file_path.startswith('\\'):
        raise ValidationError(
            message=f"File path must be relative: {file_path}",
            hint="Use relative paths without leading slash (e.g., app/main.py)",
            code="ABSOLUTE_FILE_PATH"
        )
    
    # Check for path traversal attempts
    if '..' in file_path:
        raise ValidationError(
            message=f"File path contains invalid characters: {file_path}",
            hint="Path traversal (..) is not allowed. Use relative paths within the repository",
            code="INVALID_FILE_PATH"
        )
    
    return True, None


def validate_api_query_params(
    file_path: Optional[str] = None,
    days: Optional[int] = None,
    max_files: Optional[int] = None
) -> dict:
    """Validate API query parameters and return structured errors.
    
    Args:
        file_path: Optional file path to validate
        days: Optional days parameter
        max_files: Optional max_files parameter
        
    Returns:
        Dictionary with validation results
        
    Raises:
        ValidationError: If any validation fails
    """
    errors = []
    
    try:
        if file_path is not None:
            validate_file_path(file_path)
    except ValidationError as e:
        errors.append(e.to_dict())
    
    try:
        if days is not None:
            validate_days(days)
    except ValidationError as e:
        errors.append(e.to_dict())
    
    try:
        if max_files is not None:
            validate_max_files(max_files)
    except ValidationError as e:
        errors.append(e.to_dict())
    
    if errors:
        # Return first error for simplicity
        raise ValidationError(
            message=errors[0]["error"],
            hint=errors[0]["hint"],
            code=errors[0]["code"]
        )
    
    return {"valid": True}

# Made with Bob
