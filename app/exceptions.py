"""exceptions.py

Custom exceptions for DriftGuard.
"""


class DriftGuardError(Exception):
    """Base exception for all DriftGuard errors."""
    pass


class InvalidRepositoryError(DriftGuardError):
    """Raised when repository path is invalid or not a git repository."""
    pass


class GitOperationError(DriftGuardError):
    """Raised when git operations fail."""
    pass


class AnalysisError(DriftGuardError):
    """Raised when Bob analysis fails."""
    pass


class ScoringError(DriftGuardError):
    """Raised when scoring calculation fails."""
    pass


class ReportError(DriftGuardError):
    """Raised when report generation or loading fails."""
    pass


class BobShellError(DriftGuardError):
    """Raised when Bob Shell is not available or fails."""
    pass

# Made with Bob