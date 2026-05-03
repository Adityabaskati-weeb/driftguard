"""Test language configuration system.

Tests that language configuration can be loaded from JSON,
overridden, and properly used by the git parser.
"""

import json
import tempfile
import os
from pathlib import Path
import pytest

from app.config import (
    Config,
    load_language_config,
    get_supported_extensions,
    get_extension_to_language_map,
    get_language_config_info,
    reload_language_config
)
from app.git_parser import _get_supported_extensions, _get_extension_to_language


def test_load_default_language_config():
    """Test loading default language configuration."""
    config = load_language_config()
    
    assert "version" in config
    assert "extensions" in config
    assert isinstance(config["extensions"], dict)
    
    # Check default extensions are present
    extensions = config["extensions"]
    assert ".py" in extensions
    assert ".js" in extensions
    assert ".ts" in extensions
    assert ".java" in extensions
    assert ".go" in extensions
    assert ".rb" in extensions


def test_get_supported_extensions():
    """Test getting enabled extensions."""
    extensions = get_supported_extensions()
    
    assert isinstance(extensions, set)
    assert len(extensions) > 0
    
    # Default enabled extensions should be present
    assert ".py" in extensions
    assert ".js" in extensions
    assert ".ts" in extensions


def test_get_extension_to_language_map():
    """Test getting extension to language mapping."""
    mapping = get_extension_to_language_map()
    
    assert isinstance(mapping, dict)
    assert len(mapping) > 0
    
    # Check default mappings
    assert mapping.get(".py") == "python"
    assert mapping.get(".js") == "javascript"
    assert mapping.get(".ts") == "typescript"
    assert mapping.get(".java") == "java"
    assert mapping.get(".go") == "go"
    assert mapping.get(".rb") == "ruby"


def test_get_language_config_info():
    """Test getting full language configuration info."""
    info = get_language_config_info()
    
    assert "version" in info
    assert "config_path" in info
    assert "enabled_extensions" in info
    assert "disabled_extensions" in info
    assert "total_enabled" in info
    assert "total_disabled" in info
    
    assert isinstance(info["enabled_extensions"], list)
    assert isinstance(info["disabled_extensions"], list)
    assert info["total_enabled"] > 0


def test_custom_language_config():
    """Test loading custom language configuration from file."""
    # Create temporary config file
    custom_config = {
        "version": "1.0-test",
        "description": "Test configuration",
        "extensions": {
            ".py": {"language": "python", "enabled": True, "description": "Python files"},
            ".js": {"language": "javascript", "enabled": True, "description": "JS files"},
            ".test": {"language": "testlang", "enabled": True, "description": "Test files"},
            ".disabled": {"language": "disabled", "enabled": False, "description": "Disabled"}
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(custom_config, f)
        temp_path = f.name
    
    try:
        # Override config path
        original_path = Config.LANGUAGE_CONFIG_PATH
        Config.LANGUAGE_CONFIG_PATH = Path(temp_path)
        
        # Clear caches
        Config._language_config_cache = None
        Config._supported_extensions_cache = None
        Config._extension_to_language_cache = None
        
        # Load custom config
        config = load_language_config(force_reload=True)
        
        assert config["version"] == "1.0-test"
        assert ".test" in config["extensions"]
        
        # Check enabled extensions
        extensions = get_supported_extensions()
        assert ".test" in extensions
        assert ".disabled" not in extensions
        
        # Check mapping
        mapping = get_extension_to_language_map()
        assert mapping.get(".test") == "testlang"
        assert ".disabled" not in mapping
        
    finally:
        # Restore original config
        Config.LANGUAGE_CONFIG_PATH = original_path
        Config._language_config_cache = None
        Config._supported_extensions_cache = None
        Config._extension_to_language_cache = None
        os.unlink(temp_path)


def test_git_parser_uses_config():
    """Test that git parser uses config-driven extensions."""
    # Get extensions from config
    config_extensions = get_supported_extensions()
    parser_extensions = _get_supported_extensions()
    
    # Should be the same
    assert config_extensions == parser_extensions
    
    # Get mappings
    config_mapping = get_extension_to_language_map()
    parser_mapping = _get_extension_to_language()
    
    # Should be the same
    assert config_mapping == parser_mapping


def test_reload_language_config():
    """Test reloading language configuration."""
    # Initial load
    config1 = load_language_config()
    extensions1 = get_supported_extensions()
    
    # Reload
    success, message = reload_language_config()
    
    assert success is True
    assert "reloaded successfully" in message.lower()
    
    # Should still work
    config2 = load_language_config()
    extensions2 = get_supported_extensions()
    
    assert config2 is not None
    assert len(extensions2) > 0


def test_disabled_extensions_not_included():
    """Test that disabled extensions are not included in supported set."""
    config = load_language_config()
    extensions = config.get("extensions", {})
    
    supported = get_supported_extensions()
    mapping = get_extension_to_language_map()
    
    for ext, info in extensions.items():
        if info.get("enabled", True):
            assert ext in supported
            assert ext in mapping
        else:
            assert ext not in supported
            assert ext not in mapping


def test_config_caching():
    """Test that configuration is properly cached."""
    # Clear caches
    Config._language_config_cache = None
    Config._supported_extensions_cache = None
    Config._extension_to_language_cache = None
    
    # First load
    config1 = load_language_config()
    extensions1 = get_supported_extensions()
    mapping1 = get_extension_to_language_map()
    
    # Second load (should use cache)
    config2 = load_language_config()
    extensions2 = get_supported_extensions()
    mapping2 = get_extension_to_language_map()
    
    # Should be the same objects (cached)
    assert config1 is config2
    assert extensions1 is extensions2
    assert mapping1 is mapping2


def test_invalid_config_fallback():
    """Test that invalid config falls back to defaults."""
    # Create invalid config file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write("{ invalid json }")
        temp_path = f.name
    
    try:
        # Override config path
        original_path = Config.LANGUAGE_CONFIG_PATH
        Config.LANGUAGE_CONFIG_PATH = Path(temp_path)
        
        # Clear caches
        Config._language_config_cache = None
        Config._supported_extensions_cache = None
        Config._extension_to_language_cache = None
        
        # Should fall back to defaults
        config = load_language_config(force_reload=True)
        
        assert config is not None
        assert "extensions" in config
        assert ".py" in config["extensions"]
        
    finally:
        # Restore original config
        Config.LANGUAGE_CONFIG_PATH = original_path
        Config._language_config_cache = None
        Config._supported_extensions_cache = None
        Config._extension_to_language_cache = None
        os.unlink(temp_path)


def test_missing_config_fallback():
    """Test that missing config file falls back to defaults."""
    # Override with non-existent path
    original_path = Config.LANGUAGE_CONFIG_PATH
    Config.LANGUAGE_CONFIG_PATH = Path("/nonexistent/path/config.json")
    
    try:
        # Clear caches
        Config._language_config_cache = None
        Config._supported_extensions_cache = None
        Config._extension_to_language_cache = None
        
        # Should fall back to defaults
        config = load_language_config(force_reload=True)
        
        assert config is not None
        assert "extensions" in config
        assert ".py" in config["extensions"]
        
        # Should still work
        extensions = get_supported_extensions()
        assert len(extensions) > 0
        
    finally:
        # Restore original config
        Config.LANGUAGE_CONFIG_PATH = original_path
        Config._language_config_cache = None
        Config._supported_extensions_cache = None
        Config._extension_to_language_cache = None


def test_config_info_structure():
    """Test that config info has correct structure."""
    info = get_language_config_info()
    
    # Check top-level keys
    required_keys = ["version", "description", "config_path", 
                     "enabled_extensions", "disabled_extensions",
                     "total_enabled", "total_disabled"]
    
    for key in required_keys:
        assert key in info, f"Missing key: {key}"
    
    # Check enabled extensions structure
    for ext_info in info["enabled_extensions"]:
        assert "extension" in ext_info
        assert "language" in ext_info
        assert "description" in ext_info
    
    # Check disabled extensions structure
    for ext_info in info["disabled_extensions"]:
        assert "extension" in ext_info
        assert "language" in ext_info
        assert "description" in ext_info


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("LANGUAGE CONFIGURATION TESTS")
    print("=" * 70)
    
    # Run tests
    test_load_default_language_config()
    print("✅ test_load_default_language_config")
    
    test_get_supported_extensions()
    print("✅ test_get_supported_extensions")
    
    test_get_extension_to_language_map()
    print("✅ test_get_extension_to_language_map")
    
    test_get_language_config_info()
    print("✅ test_get_language_config_info")
    
    test_custom_language_config()
    print("✅ test_custom_language_config")
    
    test_git_parser_uses_config()
    print("✅ test_git_parser_uses_config")
    
    test_reload_language_config()
    print("✅ test_reload_language_config")
    
    test_disabled_extensions_not_included()
    print("✅ test_disabled_extensions_not_included")
    
    test_config_caching()
    print("✅ test_config_caching")
    
    test_invalid_config_fallback()
    print("✅ test_invalid_config_fallback")
    
    test_missing_config_fallback()
    print("✅ test_missing_config_fallback")
    
    test_config_info_structure()
    print("✅ test_config_info_structure")
    
    print("\n" + "=" * 70)
    print("ALL TESTS PASSED!")
    print("=" * 70)

# Made with Bob
