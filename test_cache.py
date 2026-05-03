"""test_cache.py

Tests for SQLite-based analysis caching functionality.
"""
import pytest
import tempfile
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta

from app.db import (
    initialize_db,
    compute_cache_key,
    compute_diff_hash,
    get_cached_analysis,
    save_cached_analysis,
    clear_expired_cache,
    get_cache_stats,
)
from app.bob_analyzer import analyze_file_decay
from app.config import Config


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db') as f:
        db_path = f.name
    
    # Initialize the database
    initialize_db(db_path)
    
    yield db_path
    
    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


class TestCacheKeyGeneration:
    """Test cache key and diff hash generation."""
    
    def test_compute_diff_hash_stability(self):
        """Test that same diff produces same hash."""
        diff1 = "def foo():\n    return 42"
        diff2 = "def foo():\n    return 42"
        
        hash1 = compute_diff_hash(diff1)
        hash2 = compute_diff_hash(diff2)
        
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 produces 64 hex chars
    
    def test_compute_diff_hash_different(self):
        """Test that different diffs produce different hashes."""
        diff1 = "def foo():\n    return 42"
        diff2 = "def bar():\n    return 43"
        
        hash1 = compute_diff_hash(diff1)
        hash2 = compute_diff_hash(diff2)
        
        assert hash1 != hash2
    
    def test_compute_cache_key_stability(self):
        """Test that same inputs produce same cache key."""
        file_path = "app/main.py"
        diff_hash = "abc123"
        
        key1 = compute_cache_key(file_path, diff_hash)
        key2 = compute_cache_key(file_path, diff_hash)
        
        assert key1 == key2
        assert len(key1) == 64  # SHA256 produces 64 hex chars
    
    def test_compute_cache_key_different_paths(self):
        """Test that different file paths produce different keys."""
        diff_hash = "abc123"
        
        key1 = compute_cache_key("app/main.py", diff_hash)
        key2 = compute_cache_key("app/utils.py", diff_hash)
        
        assert key1 != key2
    
    def test_compute_cache_key_different_hashes(self):
        """Test that different diff hashes produce different keys."""
        file_path = "app/main.py"
        
        key1 = compute_cache_key(file_path, "abc123")
        key2 = compute_cache_key(file_path, "def456")
        
        assert key1 != key2


class TestCacheOperations:
    """Test cache storage and retrieval."""
    
    def test_cache_miss(self, temp_db):
        """Test cache miss returns None."""
        result = get_cached_analysis("app/main.py", "nonexistent_hash", db_path=temp_db)
        assert result is None
    
    def test_cache_hit(self, temp_db):
        """Test cache hit returns stored analysis."""
        file_path = "app/main.py"
        diff_hash = compute_diff_hash("def foo(): pass")
        language = "python"
        
        analysis = {
            'file_path': file_path,
            'language': language,
            'documentation_drift_score': 85,
            'test_drift_score': 70,
            'complexity_growth_score': 90,
            'naming_consistency_score': 80,
        }
        
        # Save to cache
        save_cached_analysis(file_path, diff_hash, language, analysis, temp_db)
        
        # Retrieve from cache
        cached = get_cached_analysis(file_path, diff_hash, db_path=temp_db)
        
        assert cached is not None
        assert cached['file_path'] == file_path
        assert cached['language'] == language
        assert cached['documentation_drift_score'] == 85
    
    def test_cache_overwrite(self, temp_db):
        """Test that saving same key overwrites previous entry."""
        file_path = "app/main.py"
        diff_hash = compute_diff_hash("def foo(): pass")
        language = "python"
        
        # Save first version
        analysis1 = {
            'file_path': file_path,
            'language': language,
            'documentation_drift_score': 85,
        }
        save_cached_analysis(file_path, diff_hash, language, analysis1, temp_db)
        
        # Save second version (same key)
        analysis2 = {
            'file_path': file_path,
            'language': language,
            'documentation_drift_score': 95,
        }
        save_cached_analysis(file_path, diff_hash, language, analysis2, temp_db)
        
        # Should get the second version
        cached = get_cached_analysis(file_path, diff_hash, db_path=temp_db)
        assert cached['documentation_drift_score'] == 95
    
    def test_cache_different_files(self, temp_db):
        """Test caching multiple different files."""
        files = [
            ("app/main.py", "python", "def main(): pass"),
            ("app/utils.py", "python", "def util(): pass"),
            ("app/config.py", "python", "CONFIG = {}"),
        ]
        
        for file_path, language, diff_text in files:
            diff_hash = compute_diff_hash(diff_text)
            analysis = {
                'file_path': file_path,
                'language': language,
                'documentation_drift_score': 80,
            }
            save_cached_analysis(file_path, diff_hash, language, analysis, temp_db)
        
        # Verify all are cached
        for file_path, language, diff_text in files:
            diff_hash = compute_diff_hash(diff_text)
            cached = get_cached_analysis(file_path, diff_hash, db_path=temp_db)
            assert cached is not None
            assert cached['file_path'] == file_path


class TestCacheTTL:
    """Test cache TTL (time-to-live) functionality."""
    
    def test_cache_no_expiry(self, temp_db):
        """Test cache with no TTL (None) never expires."""
        file_path = "app/main.py"
        diff_hash = compute_diff_hash("def foo(): pass")
        language = "python"
        
        analysis = {
            'file_path': file_path,
            'language': language,
            'documentation_drift_score': 85,
        }
        
        save_cached_analysis(file_path, diff_hash, language, analysis, temp_db)
        
        # Should still be valid with no TTL
        cached = get_cached_analysis(file_path, diff_hash, ttl_hours=None, db_path=temp_db)
        assert cached is not None
    
    def test_cache_within_ttl(self, temp_db):
        """Test cache is valid within TTL."""
        file_path = "app/main.py"
        diff_hash = compute_diff_hash("def foo(): pass")
        language = "python"
        
        analysis = {
            'file_path': file_path,
            'language': language,
            'documentation_drift_score': 85,
        }
        
        save_cached_analysis(file_path, diff_hash, language, analysis, temp_db)
        
        # Should be valid within 24 hours
        cached = get_cached_analysis(file_path, diff_hash, ttl_hours=24, db_path=temp_db)
        assert cached is not None
    
    def test_clear_expired_cache(self, temp_db):
        """Test clearing expired cache entries."""
        # Save some entries
        for i in range(3):
            file_path = f"app/file{i}.py"
            diff_hash = compute_diff_hash(f"def func{i}(): pass")
            analysis = {
                'file_path': file_path,
                'language': 'python',
                'documentation_drift_score': 80,
            }
            save_cached_analysis(file_path, diff_hash, 'python', analysis, temp_db)
        
        # Clear entries older than 0 hours (all of them)
        deleted = clear_expired_cache(ttl_hours=0, db_path=temp_db)
        
        # Should have deleted all 3 entries
        assert deleted == 3
        
        # Verify cache is empty
        stats = get_cache_stats(temp_db)
        assert stats['total_entries'] == 0


class TestCacheStats:
    """Test cache statistics functionality."""
    
    def test_empty_cache_stats(self, temp_db):
        """Test stats for empty cache."""
        stats = get_cache_stats(temp_db)
        
        assert stats['total_entries'] == 0
        assert stats['by_language'] == {}
        assert stats['oldest_entry'] is None
        assert stats['newest_entry'] is None
    
    def test_cache_stats_with_entries(self, temp_db):
        """Test stats with multiple entries."""
        # Add entries for different languages
        entries = [
            ("app/main.py", "python", "def main(): pass"),
            ("app/utils.py", "python", "def util(): pass"),
            ("app/script.js", "javascript", "function foo() {}"),
        ]
        
        for file_path, language, diff_text in entries:
            diff_hash = compute_diff_hash(diff_text)
            analysis = {
                'file_path': file_path,
                'language': language,
                'documentation_drift_score': 80,
            }
            save_cached_analysis(file_path, diff_hash, language, analysis, temp_db)
        
        stats = get_cache_stats(temp_db)
        
        assert stats['total_entries'] == 3
        assert stats['by_language']['python'] == 2
        assert stats['by_language']['javascript'] == 1
        assert stats['oldest_entry'] is not None
        assert stats['newest_entry'] is not None


class TestAnalyzerCacheIntegration:
    """Test cache integration with analyzer."""
    
    def test_analyzer_cache_miss_then_hit(self, temp_db):
        """Test analyzer performs analysis on cache miss, then returns cached on hit."""
        # Temporarily enable cache for this test
        original_cache_enabled = Config.CACHE_ENABLED
        Config.CACHE_ENABLED = True
        
        try:
            file_data = {
                'file_path': 'app/test.py',
                'language': 'python',
                'total_commits': 1,
                'diff_text': 'def foo():\n    return 42',
                'last_modified': '2026-05-02T10:00:00Z',
                'commit_hashes': ['abc123']
            }
            
            # First call - cache miss, performs analysis
            result1 = analyze_file_decay(file_data, use_cache=True, db_path=temp_db)
            assert result1 is not None
            assert result1['file_path'] == 'app/test.py'
            
            # Second call - cache hit, returns cached result
            result2 = analyze_file_decay(file_data, use_cache=True, db_path=temp_db)
            assert result2 is not None
            assert result2['file_path'] == 'app/test.py'
            
            # Results should be identical
            assert result1['documentation_drift_score'] == result2['documentation_drift_score']
            assert result1['test_drift_score'] == result2['test_drift_score']
            
        finally:
            Config.CACHE_ENABLED = original_cache_enabled
    
    def test_analyzer_different_diffs_different_cache(self, temp_db):
        """Test that different diffs for same file use different cache entries."""
        original_cache_enabled = Config.CACHE_ENABLED
        Config.CACHE_ENABLED = True
        
        try:
            # First version of file
            file_data1 = {
                'file_path': 'app/test.py',
                'language': 'python',
                'total_commits': 1,
                'diff_text': 'def foo():\n    return 42',
                'last_modified': '2026-05-02T10:00:00Z',
                'commit_hashes': ['abc123']
            }
            
            # Second version of file (different diff)
            file_data2 = {
                'file_path': 'app/test.py',
                'language': 'python',
                'total_commits': 2,
                'diff_text': 'def foo():\n    return 43',  # Different content
                'last_modified': '2026-05-02T11:00:00Z',
                'commit_hashes': ['abc123', 'def456']
            }
            
            # Analyze both
            result1 = analyze_file_decay(file_data1, use_cache=True, db_path=temp_db)
            result2 = analyze_file_decay(file_data2, use_cache=True, db_path=temp_db)
            
            # Should have 2 cache entries
            stats = get_cache_stats(temp_db)
            assert stats['total_entries'] == 2
            
        finally:
            Config.CACHE_ENABLED = original_cache_enabled
    
    def test_analyzer_cache_disabled(self, temp_db):
        """Test that analyzer works with cache disabled."""
        original_cache_enabled = Config.CACHE_ENABLED
        Config.CACHE_ENABLED = False
        
        try:
            file_data = {
                'file_path': 'app/test.py',
                'language': 'python',
                'total_commits': 1,
                'diff_text': 'def foo():\n    return 42',
                'last_modified': '2026-05-02T10:00:00Z',
                'commit_hashes': ['abc123']
            }
            
            # Analyze twice
            result1 = analyze_file_decay(file_data, use_cache=True, db_path=temp_db)
            result2 = analyze_file_decay(file_data, use_cache=True, db_path=temp_db)
            
            # Should have no cache entries
            stats = get_cache_stats(temp_db)
            assert stats['total_entries'] == 0
            
            # But results should still be valid
            assert result1 is not None
            assert result2 is not None
            
        finally:
            Config.CACHE_ENABLED = original_cache_enabled


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

# Made with Bob
