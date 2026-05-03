"""Simple test for parallel analysis functionality.

Tests parallel processing with a smaller set of files.
"""
import time
from typing import List, Dict

from app.bob_analyzer import batch_analyze
from app.config import Config


def generate_test_files(count: int = 20) -> List[Dict]:
    """Generate synthetic test file data.
    
    Args:
        count: Number of test files to generate
        
    Returns:
        List of file_data dicts
    """
    test_files = []
    
    # Simple diff for fast processing
    sample_diff = """
@@ -10,5 +10,15 @@ def calculate_total(items):
-def old_function():
-    pass
+def new_function(data):
+    result = []
+    for item in data:
+        if item > 0:
+            result.append(item * 2)
+    return result
"""
    
    for i in range(count):
        test_files.append({
            'file_path': f'test/module_{i:03d}.py',
            'language': 'python',
            'total_commits': 3,
            'diff_text': sample_diff,
            'last_modified': '2026-05-02T10:00:00Z',
            'commit_hashes': [f'abc{i:03d}']
        })
    
    return test_files


def test_parallel_analysis():
    """Test parallel analysis with 20+ files."""
    print("\n" + "=" * 70)
    print("Testing Parallel Analysis")
    print("=" * 70)
    
    num_files = 20
    print(f"\nConfiguration:")
    print(f"  Test files: {num_files}")
    print(f"  Max workers: {Config.MAX_WORKERS}")
    print(f"  Rate limit: {Config.BOB_RATE_LIMIT_PER_MINUTE} calls/min")
    
    # Generate test data
    print(f"\nGenerating {num_files} test files...")
    test_files = generate_test_files(num_files)
    print(f"Generated {len(test_files)} test files")
    
    # Test sequential (1 worker)
    print("\n" + "-" * 70)
    print("Sequential Analysis (1 worker)")
    print("-" * 70)
    start = time.time()
    seq_results = batch_analyze(test_files, max_workers=1)
    seq_duration = time.time() - start
    print(f"\nSequential: {seq_duration:.2f}s, {len(seq_results)} files")
    
    # Brief delay
    time.sleep(1)
    
    # Test parallel (default workers)
    print("\n" + "-" * 70)
    print(f"Parallel Analysis ({Config.MAX_WORKERS} workers)")
    print("-" * 70)
    start = time.time()
    par_results = batch_analyze(test_files, max_workers=Config.MAX_WORKERS)
    par_duration = time.time() - start
    print(f"\nParallel: {par_duration:.2f}s, {len(par_results)} files")
    
    # Calculate speedup
    print("\n" + "=" * 70)
    print("Results")
    print("=" * 70)
    
    if par_duration > 0:
        speedup = seq_duration / par_duration
        print(f"Sequential time: {seq_duration:.2f}s")
        print(f"Parallel time:   {par_duration:.2f}s")
        print(f"Speedup:         {speedup:.2f}x")
        print(f"Time saved:      {seq_duration - par_duration:.2f}s")
    
    # Verify deterministic output
    print("\nDeterminism Check:")
    if len(seq_results) == len(par_results):
        all_match = True
        for i, (s, p) in enumerate(zip(seq_results, par_results)):
            if s.get('file_path') != p.get('file_path'):
                print(f"  Order mismatch at index {i}")
                all_match = False
                break
        
        if all_match:
            print("  [OK] Results are in same order (deterministic)")
        else:
            print("  [FAIL] Results order differs")
    else:
        print(f"  [FAIL] Different number of results: {len(seq_results)} vs {len(par_results)}")
    
    # Verify all files were analyzed
    print(f"\nFiles analyzed: {len(par_results)}/{num_files}")
    if len(par_results) == num_files:
        print("[OK] All files analyzed successfully")
    else:
        print("[FAIL] Some files failed to analyze")
    
    print("\n" + "=" * 70)
    print("Test Complete!")
    print("=" * 70 + "\n")


if __name__ == '__main__':
    test_parallel_analysis()

# Made with Bob
