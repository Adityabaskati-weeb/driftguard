"""config.py

Load and manage application configuration from environment, CLI, and defaults.
"""
import os
import json
from pathlib import Path
from typing import Optional, List, Dict, Set, Tuple
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
    
    # Analysis cache settings
    CACHE_ENABLED = os.getenv("DRIFTGUARD_CACHE_ENABLED", "true").lower() == "true"
    CACHE_TTL_HOURS = int(os.getenv("DRIFTGUARD_CACHE_TTL_HOURS", "0"))  # 0 = no expiry
    
    # Rate limiting settings for Bob analysis calls
    BOB_RATE_LIMIT_PER_MINUTE = int(os.getenv("BOB_RATE_LIMIT_PER_MINUTE", "30"))  # Max calls per minute
    BOB_RATE_LIMIT_BURST = int(os.getenv("BOB_RATE_LIMIT_BURST", "5"))  # Burst capacity
    
    # Parallel processing settings
    # Language configuration file path
    LANGUAGE_CONFIG_PATH = Path(os.getenv(
        "DRIFTGUARD_LANGUAGE_CONFIG",
        str(DATA_DIR / "language_config.json")
    ))
    
    # Cached language configuration
    _language_config_cache: Optional[Dict] = None
    _supported_extensions_cache: Optional[Set[str]] = None
    _extension_to_language_cache: Optional[Dict[str, str]] = None


def load_language_config(force_reload: bool = False) -> Dict:
    """Load language configuration from JSON file.
    
    Args:
        force_reload: Force reload from disk even if cached
        
    Returns:
        Dictionary containing language configuration
    """
    if not force_reload and Config._language_config_cache is not None:
        return Config._language_config_cache
    
    config_path = Config.LANGUAGE_CONFIG_PATH
    
    # Default configuration if file doesn't exist
    default_config = {
        "version": "1.0",
        "description": "Default language configuration",
        "extensions": {
            ".py": {"language": "python", "enabled": True, "description": "Python source files"},
            ".js": {"language": "javascript", "enabled": True, "description": "JavaScript source files"},
            ".ts": {"language": "typescript", "enabled": True, "description": "TypeScript source files"},
            ".java": {"language": "java", "enabled": True, "description": "Java source files"},
            ".go": {"language": "go", "enabled": True, "description": "Go source files"},
            ".rb": {"language": "ruby", "enabled": True, "description": "Ruby source files"},
            ".html": {"language": "html", "enabled": True, "description": "HTML files"},
            ".css": {"language": "css", "enabled": True, "description": "CSS stylesheets"},
        }
    }
    
    if not config_path.exists():
        print(f"Warning: Language config not found at {config_path}, using defaults")
        Config._language_config_cache = default_config
        return default_config
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            Config._language_config_cache = config
            return config
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Failed to load language config from {config_path}: {e}")
        print("Using default configuration")
        Config._language_config_cache = default_config
        return default_config


def get_supported_extensions() -> Set[str]:
    """Get set of enabled file extensions.
    
    Returns:
        Set of file extensions (e.g., {'.py', '.js', '.ts'})
    """
    if Config._supported_extensions_cache is not None:
        return Config._supported_extensions_cache
    
    config = load_language_config()
    extensions = config.get("extensions", {})
    
    supported = {
        ext for ext, info in extensions.items()
        if info.get("enabled", True)
    }
    
    Config._supported_extensions_cache = supported
    return supported


def get_extension_to_language_map() -> Dict[str, str]:
    """Get mapping of file extensions to language names.
    
    Returns:
        Dictionary mapping extensions to language names (e.g., {'.py': 'python'})
    """
    if Config._extension_to_language_cache is not None:
        return Config._extension_to_language_cache
    
    config = load_language_config()
    extensions = config.get("extensions", {})
    
    mapping = {
        ext: info.get("language", "unknown")
        for ext, info in extensions.items()
        if info.get("enabled", True)
    }
    
    Config._extension_to_language_cache = mapping
    return mapping


def get_language_config_info() -> Dict:
    """Get full language configuration information for display.
    
    Returns:
        Dictionary with configuration details including enabled/disabled extensions
    """
    config = load_language_config()
    extensions = config.get("extensions", {})
    
    enabled = []
    disabled = []
    
    for ext, info in sorted(extensions.items()):
        entry = {
            "extension": ext,
            "language": info.get("language", "unknown"),
            "description": info.get("description", "")
        }
        
        if info.get("enabled", True):
            enabled.append(entry)
        else:
            disabled.append(entry)
    
    return {
        "version": config.get("version", "unknown"),
        "description": config.get("description", ""),
        "config_path": str(Config.LANGUAGE_CONFIG_PATH),
        "enabled_extensions": enabled,
        "disabled_extensions": disabled,
        "total_enabled": len(enabled),
        "total_disabled": len(disabled)
    }


def reload_language_config() -> Tuple[bool, str]:
    """Reload language configuration from disk.
    
    Returns:
        Tuple of (success, message)
    """
    try:
        # Clear caches
        Config._language_config_cache = None
        Config._supported_extensions_cache = None
        Config._extension_to_language_cache = None
        
        # Reload
        config = load_language_config(force_reload=True)
        enabled_count = len(get_supported_extensions())
        
        return True, f"Language configuration reloaded successfully. {enabled_count} extensions enabled."
    except Exception as e:
        return False, f"Failed to reload language configuration: {str(e)}"

    MAX_WORKERS = int(os.getenv("DRIFTGUARD_MAX_WORKERS", str(min(8, os.cpu_count() or 1))))  # Parallel analysis workers


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
