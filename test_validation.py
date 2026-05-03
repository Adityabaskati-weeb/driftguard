"""test_validation.py

Tests for input validation with user-friendly error messages.
"""
import pytest
import tempfile
import os
from pathlib import Path

from app.validation import (
    ValidationError,
    validate_repo_path,
    validate_days,
    validate_max_files,
    validate_interval,
    validate_export_mode,
    validate_file_path,
    validate_api_query_params
)


class TestRepoValidation:
    """Test repository path validation."""
    
    def test_valid_local_repo(self, tmp_path):
        """Test validation of valid local git repository."""
        # Create a mock git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        
        # Should not raise
        is_valid, error = validate_repo_path(str(tmp_path))
        assert is_valid is True
        assert error is None
    
    def test_nonexistent_path(self):
        """Test validation fails for nonexistent path."""
        with pytest.raises(ValidationError) as exc_info:
            validate_repo_path("/nonexistent/path/to/repo")
        
        assert exc_info.value.code == "REPO_NOT_FOUND"
        assert "does not exist" in exc_info.value.message
        assert "Ensure the path exists" in exc_info.value.hint
    
    def test_not_a_directory(self, tmp_path):
        """Test validation fails for file instead of directory."""
        # Create a file
        file_path = tmp_path / "test.txt"
        file_path.write_text("test")
        
        with pytest.raises(ValidationError) as exc_info:
            validate_repo_path(str(file_path))
        
        assert exc_info.value.code == "REPO_NOT_DIRECTORY"
        assert "not a directory" in exc_info.value.message
        assert "directory containing a git repository" in exc_info.value.hint
    
    def test_not_a_git_repo(self, tmp_path):
        """Test validation fails for directory without .git."""
        with pytest.raises(ValidationError) as exc_info:
            validate_repo_path(str(tmp_path))
        
        assert exc_info.value.code == "NOT_GIT_REPO"
        assert "Not a git repository" in exc_info.value.message
        assert "git init" in exc_info.value.hint
    
    def test_valid_github_https_url(self):
        """Test validation of valid GitHub HTTPS URL."""
        is_valid, error = validate_repo_path("https://github.com/owner/repo")
        assert is_valid is True
        assert error is None
    
    def test_valid_github_https_url_with_git(self):
        """Test validation of valid GitHub HTTPS URL with .git suffix."""
        is_valid, error = validate_repo_path("https://github.com/owner/repo.git")
        assert is_valid is True
        assert error is None
    
    def test_valid_github_ssh_url(self):
        """Test validation of valid GitHub SSH URL."""
        is_valid, error = validate_repo_path("git@github.com:owner/repo")
        assert is_valid is True
        assert error is None
    
    def test_invalid_url_format(self):
        """Test validation fails for invalid URL format."""
        with pytest.raises(ValidationError) as exc_info:
            validate_repo_path("not-a-valid-url")
        
        assert exc_info.value.code in ["REPO_NOT_FOUND", "NOT_GIT_REPO"]


class TestDaysValidation:
    """Test days parameter validation."""
    
    def test_valid_days(self):
        """Test validation of valid days value."""
        is_valid, error = validate_days(30)
        assert is_valid is True
        assert error is None
    
    def test_invalid_type(self):
        """Test validation fails for non-integer type."""
        with pytest.raises(ValidationError) as exc_info:
            validate_days("30")
        
        assert exc_info.value.code == "INVALID_DAYS_TYPE"
        assert "must be an integer" in exc_info.value.message
        assert "positive integer" in exc_info.value.hint
    
    def test_zero_days(self):
        """Test validation fails for zero days."""
        with pytest.raises(ValidationError) as exc_info:
            validate_days(0)
        
        assert exc_info.value.code == "INVALID_DAYS_VALUE"
        assert "must be positive" in exc_info.value.message
        assert "positive number" in exc_info.value.hint
    
    def test_negative_days(self):
        """Test validation fails for negative days."""
        with pytest.raises(ValidationError) as exc_info:
            validate_days(-10)
        
        assert exc_info.value.code == "INVALID_DAYS_VALUE"
        assert "must be positive" in exc_info.value.message
    
    def test_days_too_large(self):
        """Test validation fails for days > 365."""
        with pytest.raises(ValidationError) as exc_info:
            validate_days(400)
        
        assert exc_info.value.code == "DAYS_TOO_LARGE"
        assert "cannot exceed 365" in exc_info.value.message
        assert "may be slow" in exc_info.value.hint


class TestMaxFilesValidation:
    """Test max_files parameter validation."""
    
    def test_valid_max_files(self):
        """Test validation of valid max_files value."""
        is_valid, error = validate_max_files(20)
        assert is_valid is True
        assert error is None
    
    def test_invalid_type(self):
        """Test validation fails for non-integer type."""
        with pytest.raises(ValidationError) as exc_info:
            validate_max_files("20")
        
        assert exc_info.value.code == "INVALID_MAX_FILES_TYPE"
        assert "must be an integer" in exc_info.value.message
    
    def test_zero_max_files(self):
        """Test validation fails for zero max_files."""
        with pytest.raises(ValidationError) as exc_info:
            validate_max_files(0)
        
        assert exc_info.value.code == "INVALID_MAX_FILES_VALUE"
        assert "must be positive" in exc_info.value.message
    
    def test_negative_max_files(self):
        """Test validation fails for negative max_files."""
        with pytest.raises(ValidationError) as exc_info:
            validate_max_files(-5)
        
        assert exc_info.value.code == "INVALID_MAX_FILES_VALUE"
        assert "must be positive" in exc_info.value.message
    
    def test_max_files_too_large(self):
        """Test validation fails for max_files > 100."""
        with pytest.raises(ValidationError) as exc_info:
            validate_max_files(150)
        
        assert exc_info.value.code == "MAX_FILES_TOO_LARGE"
        assert "cannot exceed 100" in exc_info.value.message
        assert "may be slow" in exc_info.value.hint


class TestIntervalValidation:
    """Test interval parameter validation."""
    
    def test_valid_hours(self):
        """Test validation of valid hours format."""
        is_valid, error = validate_interval("24h")
        assert is_valid is True
        assert error is None
    
    def test_valid_minutes(self):
        """Test validation of valid minutes format."""
        is_valid, error = validate_interval("30m")
        assert is_valid is True
        assert error is None
    
    def test_valid_seconds(self):
        """Test validation of valid seconds format."""
        is_valid, error = validate_interval("3600s")
        assert is_valid is True
        assert error is None
    
    def test_valid_plain_number(self):
        """Test validation of valid plain number (seconds)."""
        is_valid, error = validate_interval("3600")
        assert is_valid is True
        assert error is None
    
    def test_invalid_format(self):
        """Test validation fails for invalid format."""
        with pytest.raises(ValidationError) as exc_info:
            validate_interval("24hours")
        
        assert exc_info.value.code == "INVALID_INTERVAL_FORMAT"
        assert "Invalid interval format" in exc_info.value.message
        assert "'24h'" in exc_info.value.hint
    
    def test_zero_interval(self):
        """Test validation fails for zero interval."""
        with pytest.raises(ValidationError) as exc_info:
            validate_interval("0h")
        
        assert exc_info.value.code == "INVALID_INTERVAL_VALUE"
        assert "must be positive" in exc_info.value.message
    
    def test_negative_interval(self):
        """Test validation fails for negative interval."""
        with pytest.raises(ValidationError) as exc_info:
            validate_interval("-10")
        
        assert exc_info.value.code == "INVALID_INTERVAL_VALUE"
        assert "must be positive" in exc_info.value.message
    
    def test_interval_too_short(self):
        """Test validation fails for interval < 60 seconds."""
        with pytest.raises(ValidationError) as exc_info:
            validate_interval("30s")
        
        assert exc_info.value.code == "INTERVAL_TOO_SHORT"
        assert "too short" in exc_info.value.message
        assert "Minimum interval is 60 seconds" in exc_info.value.hint
    
    def test_interval_too_short_plain_number(self):
        """Test validation fails for plain number < 60."""
        with pytest.raises(ValidationError) as exc_info:
            validate_interval("30")
        
        assert exc_info.value.code == "INTERVAL_TOO_SHORT"
        assert "too short" in exc_info.value.message


class TestExportModeValidation:
    """Test export mode parameter validation."""
    
    def test_valid_json(self):
        """Test validation of json export mode."""
        is_valid, error = validate_export_mode("json")
        assert is_valid is True
        assert error is None
    
    def test_valid_markdown(self):
        """Test validation of markdown export mode."""
        is_valid, error = validate_export_mode("markdown")
        assert is_valid is True
        assert error is None
    
    def test_valid_pdf(self):
        """Test validation of pdf export mode."""
        is_valid, error = validate_export_mode("pdf")
        assert is_valid is True
        assert error is None
    
    def test_valid_all(self):
        """Test validation of all export mode."""
        is_valid, error = validate_export_mode("all")
        assert is_valid is True
        assert error is None
    
    def test_invalid_mode(self):
        """Test validation fails for invalid export mode."""
        with pytest.raises(ValidationError) as exc_info:
            validate_export_mode("xml")
        
        assert exc_info.value.code == "INVALID_EXPORT_MODE"
        assert "Invalid export mode" in exc_info.value.message
        assert "json, markdown, pdf, all" in exc_info.value.hint


class TestFilePathValidation:
    """Test file path parameter validation."""
    
    def test_valid_file_path(self):
        """Test validation of valid file path."""
        is_valid, error = validate_file_path("app/main.py")
        assert is_valid is True
        assert error is None
    
    def test_empty_file_path(self):
        """Test validation fails for empty file path."""
        with pytest.raises(ValidationError) as exc_info:
            validate_file_path("")
        
        assert exc_info.value.code == "EMPTY_FILE_PATH"
        assert "cannot be empty" in exc_info.value.message
    
    def test_absolute_path_unix(self):
        """Test validation fails for absolute Unix path."""
        with pytest.raises(ValidationError) as exc_info:
            validate_file_path("/app/main.py")
        
        assert exc_info.value.code == "ABSOLUTE_FILE_PATH"
        assert "must be relative" in exc_info.value.message
        assert "without leading slash" in exc_info.value.hint
    
    def test_absolute_path_windows(self):
        """Test validation fails for absolute Windows path."""
        with pytest.raises(ValidationError) as exc_info:
            validate_file_path("\\app\\main.py")
        
        assert exc_info.value.code == "ABSOLUTE_FILE_PATH"
        assert "must be relative" in exc_info.value.message
    
    def test_path_traversal(self):
        """Test validation fails for path traversal."""
        with pytest.raises(ValidationError) as exc_info:
            validate_file_path("../../../etc/passwd")
        
        assert exc_info.value.code == "INVALID_FILE_PATH"
        assert "invalid characters" in exc_info.value.message
        assert "not allowed" in exc_info.value.hint


class TestValidationErrorStructure:
    """Test ValidationError structure and methods."""
    
    def test_error_to_dict(self):
        """Test ValidationError.to_dict() returns correct structure."""
        error = ValidationError(
            message="Test error",
            hint="Test hint",
            code="TEST_ERROR"
        )
        
        error_dict = error.to_dict()
        assert error_dict["error"] == "Test error"
        assert error_dict["hint"] == "Test hint"
        assert error_dict["code"] == "TEST_ERROR"
    
    def test_error_default_code(self):
        """Test ValidationError uses default code."""
        error = ValidationError(message="Test error")
        assert error.code == "VALIDATION_ERROR"
        assert error.hint == ""
    
    def test_error_str_representation(self):
        """Test ValidationError string representation."""
        error = ValidationError(message="Test error")
        assert str(error) == "Test error"


class TestAPIQueryParamsValidation:
    """Test API query parameters validation."""
    
    def test_valid_all_params(self):
        """Test validation of all valid parameters."""
        result = validate_api_query_params(
            file_path="app/main.py",
            days=30,
            max_files=20
        )
        assert result["valid"] is True
    
    def test_invalid_file_path(self):
        """Test validation fails for invalid file path."""
        with pytest.raises(ValidationError) as exc_info:
            validate_api_query_params(file_path="../etc/passwd")
        
        assert exc_info.value.code == "INVALID_FILE_PATH"
    
    def test_invalid_days(self):
        """Test validation fails for invalid days."""
        with pytest.raises(ValidationError) as exc_info:
            validate_api_query_params(days=-10)
        
        assert exc_info.value.code == "INVALID_DAYS_VALUE"
    
    def test_invalid_max_files(self):
        """Test validation fails for invalid max_files."""
        with pytest.raises(ValidationError) as exc_info:
            validate_api_query_params(max_files=0)
        
        assert exc_info.value.code == "INVALID_MAX_FILES_VALUE"
    
    def test_none_params_allowed(self):
        """Test None parameters are allowed (optional)."""
        result = validate_api_query_params(
            file_path=None,
            days=None,
            max_files=None
        )
        assert result["valid"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# Made with Bob
