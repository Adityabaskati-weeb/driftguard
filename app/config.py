"""config.py

Load and manage application configuration from environment, CLI, and defaults.
"""
import os
import json
from pathlib import Path
from typing import Optional, List, Dict
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()


class Config:
    """Centralized configuration management."""
    
    # Directories
    REPO_ROOT = Path(__file__).parent.parent
    APP_DIR = REPO_ROOT / "app"
    OUTPUT_DIR = REPO_ROOT / "output"
    BOB_SESSIONS_DIR = REPO_ROOT / "bob_sessions"
    TEMPLATES_DIR = APP_DIR / "templates"
    DATA_DIR = REPO_ROOT / "data"
    
    # Create directories if they don't exist
    OUTPUT_DIR.mkdir(exist_ok=True)
    BOB_SESSIONS_DIR.mkdir(exist_ok=True)
    DATA_DIR.mkdir(exist_ok=True)
    
    # API Key
    API_KEY = os.getenv("DRIFTGUARD_API_KEY", "")
    
    # Repos configuration file
    REPOS_JSON_PATH = DATA_DIR / "repos.json"
    
    # Analysis defaults
    DEFAULT_DAYS = int(os.getenv("DRIFTGUARD_DAYS", "30"))
    DEFAULT_MAX_FILES = int(os.getenv("DRIFTGUARD_MAX_FILES", "20"))
    DEFAULT_REPO_PATH = os.getenv("DRIFTGUARD_REPO", ".")
    
    # Logging
    LOG_LEVEL = os.getenv("DRIFTGUARD_LOG_LEVEL", "INFO")
    
    # FastAPI
    FASTAPI_HOST = os.getenv("DRIFTGUARD_HOST", "127.0.0.1")
    FASTAPI_PORT = int(os.getenv("DRIFTGUARD_PORT", "8000"))
    FASTAPI_RELOAD = os.getenv("DRIFTGUARD_RELOAD", "true").lower() == "true"
    
    # File extensions to analyze
    ALLOWED_EXTENSIONS = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".java": "java",
        ".go": "go",
        ".rb": "ruby",
    }
    
    # Language-specific thresholds for complexity and function length
    LANGUAGE_THRESHOLDS = {
        "python": {
            "max_function_lines": 50,
            "max_class_lines": 200,
            "max_nesting_depth": 4,
            "complexity_threshold": 150,
        },
        "javascript": {
            "max_function_lines": 40,
            "max_class_lines": 150,
            "max_nesting_depth": 3,
            "complexity_threshold": 150,
        },
        "typescript": {
            "max_function_lines": 40,
            "max_class_lines": 150,
            "max_nesting_depth": 3,
            "complexity_threshold": 150,
        },
        "java": {
            "max_function_lines": 50,
            "max_class_lines": 300,
            "max_nesting_depth": 4,
            "complexity_threshold": 300,
        },
        "go": {
            "max_function_lines": 50,
            "max_class_lines": 200,
            "max_nesting_depth": 3,
            "complexity_threshold": 150,
        },
        "ruby": {
            "max_function_lines": 25,
            "max_class_lines": 150,
            "max_nesting_depth": 3,
            "complexity_threshold": 100,
        },
    }
    
    # Scoring thresholds
    SCORE_CRITICAL_THRESHOLD = 40        # 0-39 = CRITICAL
    SCORE_AT_RISK_THRESHOLD = 60         # 40-59 = AT_RISK
    SCORE_WATCH_THRESHOLD = 80           # 60-79 = WATCH
    # 80-100 = HEALTHY
    
    # Score weights (must sum to 1.0)
    WEIGHT_DOCUMENTATION = 0.30
    WEIGHT_TEST_COVERAGE = 0.30
    WEIGHT_COMPLEXITY = 0.25
    WEIGHT_NAMING = 0.15
    
    # Status emojis
    STATUS_EMOJI = {
        "CRITICAL": "🔴",
        "AT_RISK": "🟠",
        "WATCH": "🟡",
        "HEALTHY": "🟢",
    }
    
    # Rule-based analyzer thresholds
    RULE_DOC_DRIFT_THRESHOLD_ADDED_LINES = 50      # if 50+ lines added with 0 comments
    RULE_COMPLEXITY_NESTING_THRESHOLD = 2          # nesting level increase
    RULE_TEST_REQUIRED_RATIO = 0.3                 # if changed code vs test code ratio


def get_output_report_path(timestamp: Optional[str] = None) -> Path:
    """Generate output report file path with timestamp."""
    from datetime import datetime
    if timestamp is None:
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return Config.OUTPUT_DIR / f"report_{timestamp}.json"


def get_latest_report() -> Optional[Path]:
    """Find the most recent report JSON file in output directory."""
    if not Config.OUTPUT_DIR.exists():
        return None
    reports = list(Config.OUTPUT_DIR.glob("report_*.json"))
    if not reports:
        return None
    return max(reports, key=lambda p: p.stat().st_mtime)



def load_repos_config() -> List[Dict]:
    """Load repository configuration from repos.json.
    
    Returns:
        List of repository configurations with name, path, days, and enabled status.
    """
    if not Config.REPOS_JSON_PATH.exists():
        # Return default config if file doesn't exist
        return [{
            "name": "default",
            "path": Config.DEFAULT_REPO_PATH,
            "days": Config.DEFAULT_DAYS,
            "enabled": True
        }]
    
    try:
        with open(Config.REPOS_JSON_PATH, 'r') as f:
            repos = json.load(f)
            # Filter only enabled repos
            return [repo for repo in repos if repo.get('enabled', True)]
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Failed to load repos.json: {e}")
        return [{
            "name": "default",
            "path": Config.DEFAULT_REPO_PATH,
            "days": Config.DEFAULT_DAYS,
            "enabled": True
        }]
