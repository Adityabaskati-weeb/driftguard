"""demo_cache.py

Demonstration of the SQLite-based analysis caching functionality.
Shows cache hits, misses, and performance improvements.
"""
import time
from app.db import (
    initialize_db,
    get_cache_stats,
    clear_expired_cache,
    DEFAULT_DB_PATH
)
from app.bob_analyzer import analyze_file_decay
from app.config import Config


def demo_cache():
    """Demonstrate caching functionality."""
    print("=" * 70)
    print("DriftGuard Analysis Cache Demonstration")
    print("=" * 70)
    
    # Initialize database
    print("\n[1] Initializing database...")
    initialize_db(DEFAULT_DB_PATH)
    print("    [OK] Database initialized")
    
    # Show initial cache stats
    print("\n[2] Initial cache statistics:")
    stats = get_cache_stats(DEFAULT_DB_PATH)
    print(f"    Total entries: {stats['total_entries']}")
    print(f"    By language: {stats['by_language']}")
    
    # Sample file data
    sample_file = {
        'file_path': 'app/demo.py',
        'language': 'python',
        'total_commits': 5,
        'diff_text': '''
@@ -10,5 +10,25 @@ def calculate_total(items):
-def old_function():
-    pass
+def new_complex_function(data):
+    """Process data with complex logic."""
+    result = []
+    for item in data:
+        if item > 0:
+            for subitem in item.values():
+                if subitem:
+                    result.append(subitem * 100)
+    return result
+
+def helper_function(x):
+    return x * 42
        ''',
        'last_modified': '2026-05-02T10:00:00Z',
        'commit_hashes': ['abc123', 'def456', 'ghi789']
    }
    
    # Enable cache for demo
    original_cache_enabled = Config.CACHE_ENABLED
    Config.CACHE_ENABLED = True
    
    try:
        print("\n[3] First analysis (cache miss)...")
        start_time = time.time()
        result1 = analyze_file_decay(sample_file, use_cache=True, db_path=DEFAULT_DB_PATH)
        first_duration = time.time() - start_time
        print(f"    [OK] Analysis completed in {first_duration:.4f} seconds")
        print(f"    Documentation score: {result1['documentation_drift_score']}")
        print(f"    Test score: {result1['test_drift_score']}")
        print(f"    Complexity score: {result1['complexity_growth_score']}")
        print(f"    Naming score: {result1['naming_consistency_score']}")
        
        print("\n[4] Second analysis (cache hit)...")
        start_time = time.time()
        result2 = analyze_file_decay(sample_file, use_cache=True, db_path=DEFAULT_DB_PATH)
        second_duration = time.time() - start_time
        print(f"    [OK] Analysis completed in {second_duration:.4f} seconds")
        print(f"    Documentation score: {result2['documentation_drift_score']}")
        print(f"    Test score: {result2['test_drift_score']}")
        print(f"    Complexity score: {result2['complexity_growth_score']}")
        print(f"    Naming score: {result2['naming_consistency_score']}")
        
        # Verify results are identical
        scores_match = (
            result1['documentation_drift_score'] == result2['documentation_drift_score'] and
            result1['test_drift_score'] == result2['test_drift_score'] and
            result1['complexity_growth_score'] == result2['complexity_growth_score'] and
            result1['naming_consistency_score'] == result2['naming_consistency_score']
        )
        
        print(f"\n[5] Cache performance:")
        if second_duration > 0:
            speedup = first_duration / second_duration
            print(f"    Cache speedup: {speedup:.1f}x faster")
        print(f"    Results identical: {'YES' if scores_match else 'NO'}")
        
        print("\n[6] Updated cache statistics:")
        stats = get_cache_stats(DEFAULT_DB_PATH)
        print(f"    Total entries: {stats['total_entries']}")
        print(f"    By language: {stats['by_language']}")
        print(f"    Oldest entry: {stats['oldest_entry']}")
        print(f"    Newest entry: {stats['newest_entry']}")
        
        # Test different file (should create new cache entry)
        print("\n[7] Analyzing different file...")
        different_file = sample_file.copy()
        different_file['file_path'] = 'app/different.py'
        different_file['diff_text'] = 'def simple_function():\n    return "hello"'
        
        result3 = analyze_file_decay(different_file, use_cache=True, db_path=DEFAULT_DB_PATH)
        print(f"    [OK] Different file analyzed")
        
        print("\n[8] Final cache statistics:")
        stats = get_cache_stats(DEFAULT_DB_PATH)
        print(f"    Total entries: {stats['total_entries']}")
        print(f"    By language: {stats['by_language']}")
        
        # Test cache with TTL
        print("\n[9] Testing cache expiry...")
        expired_count = clear_expired_cache(ttl_hours=0, db_path=DEFAULT_DB_PATH)
        print(f"    [OK] Cleared {expired_count} expired entries")
        
        stats = get_cache_stats(DEFAULT_DB_PATH)
        print(f"    Remaining entries: {stats['total_entries']}")
        
    finally:
        Config.CACHE_ENABLED = original_cache_enabled
    
    print("\n" + "=" * 70)
    print("Cache demonstration complete!")
    print("=" * 70)
    
    print("\nKey benefits of analysis caching:")
    print("• Faster repeated analyses of same file/diff combinations")
    print("• Reduced computational overhead for large repositories")
    print("• Configurable TTL for cache expiry")
    print("• Automatic cache key generation based on file path + diff hash")
    print("• Same output shape as non-cached analysis")


if __name__ == '__main__':
    demo_cache()

# Made with Bob
