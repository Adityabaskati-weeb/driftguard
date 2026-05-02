"""test_integration_trends.py

Integration test for trends and baseline features.
"""

import json
import sqlite3
import sys
from pathlib import Path
from app.baseline_profile import build_baseline, load_baseline
from app.bob_analyzer import set_baseline, get_baseline
from app.trends import compute_trends, detect_trend_direction, compute_trend_adjustment
from app.scorer import calculate_health_score
from app import db

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')


def test_baseline_integration():
    """Test baseline profile creation and loading."""
    print("\n" + "="*70)
    print("TEST 1: Baseline Profile Integration")
    print("="*70)
    
    # Build baseline
    print("\n1. Building baseline profile...")
    baseline = build_baseline('.')
    print(f"   ✓ Baseline created with {baseline['total_files']} files")
    print(f"   ✓ Docstring coverage: {baseline['docstring_coverage_pct']}%")
    print(f"   ✓ Dominant naming style: {baseline['dominant_naming_style']}")
    
    # Load baseline
    print("\n2. Loading baseline profile...")
    loaded = load_baseline('.')
    assert loaded is not None, "Failed to load baseline"
    assert loaded['total_files'] == baseline['total_files']
    print("   ✓ Baseline loaded successfully")
    
    # Set baseline in analyzer
    print("\n3. Setting baseline in analyzer...")
    set_baseline('.')
    analyzer_baseline = get_baseline()
    assert analyzer_baseline is not None, "Failed to set baseline in analyzer"
    print("   ✓ Baseline set in analyzer")
    
    print("\n✅ Baseline integration test PASSED\n")


def test_trend_detection():
    """Test trend detection logic."""
    print("\n" + "="*70)
    print("TEST 2: Trend Detection Logic")
    print("="*70)
    
    # Test improving trend
    print("\n1. Testing improving trend...")
    improving_scores = [60.0, 65.0, 72.0]
    direction = detect_trend_direction(improving_scores)
    assert direction == "improving", f"Expected 'improving', got '{direction}'"
    print(f"   ✓ Detected: {direction}")
    
    # Test declining trend
    print("\n2. Testing declining trend...")
    declining_scores = [80.0, 72.0, 65.0]
    direction = detect_trend_direction(declining_scores)
    assert direction == "declining", f"Expected 'declining', got '{direction}'"
    print(f"   ✓ Detected: {direction}")
    
    # Test stable trend
    print("\n3. Testing stable trend...")
    stable_scores = [70.0, 72.0, 71.0]
    direction = detect_trend_direction(stable_scores)
    assert direction == "stable", f"Expected 'stable', got '{direction}'"
    print(f"   ✓ Detected: {direction}")
    
    print("\n✅ Trend detection test PASSED\n")


def test_trend_adjustment():
    """Test trend adjustment penalties."""
    print("\n" + "="*70)
    print("TEST 3: Trend Adjustment Penalties")
    print("="*70)
    
    # Test no penalty for improving
    print("\n1. Testing no penalty for improving trend...")
    trend_data = {'score_change': 10.0, 'trend_direction': 'improving'}
    penalty = compute_trend_adjustment(trend_data)
    assert penalty == 0.0, f"Expected 0.0, got {penalty}"
    print(f"   ✓ Penalty: {penalty} points")
    
    # Test severe decline penalty
    print("\n2. Testing severe decline penalty...")
    trend_data = {'score_change': -25.0, 'trend_direction': 'declining'}
    penalty = compute_trend_adjustment(trend_data)
    assert penalty == 15.0, f"Expected 15.0, got {penalty}"
    print(f"   ✓ Penalty: {penalty} points")
    
    # Test moderate decline penalty
    print("\n3. Testing moderate decline penalty...")
    trend_data = {'score_change': -12.0, 'trend_direction': 'declining'}
    penalty = compute_trend_adjustment(trend_data)
    assert penalty == 10.0, f"Expected 10.0, got {penalty}"
    print(f"   ✓ Penalty: {penalty} points")
    
    print("\n✅ Trend adjustment test PASSED\n")


def test_scorer_with_trends():
    """Test scorer with trend adjustments."""
    print("\n" + "="*70)
    print("TEST 4: Scorer with Trend Adjustments")
    print("="*70)
    
    # Create sample analysis
    analysis = {
        'file_path': 'test.py',
        'documentation_drift_score': 70,
        'test_drift_score': 65,
        'complexity_growth_score': 75,
        'naming_consistency_score': 80
    }
    
    # Calculate without trend adjustment
    print("\n1. Calculating health score without trend adjustment...")
    result1 = calculate_health_score(analysis.copy(), trend_adjustment=0.0)
    base_score = result1['health_score']
    print(f"   ✓ Base health score: {base_score}")
    
    # Calculate with trend adjustment
    print("\n2. Calculating health score with trend adjustment...")
    result2 = calculate_health_score(analysis.copy(), trend_adjustment=10.0)
    adjusted_score = result2['health_score']
    print(f"   ✓ Adjusted health score: {adjusted_score}")
    print(f"   ✓ Penalty applied: {base_score - adjusted_score} points")
    
    assert adjusted_score < base_score, "Adjusted score should be lower"
    assert result2['trend_penalty'] == 10.0, "Trend penalty not recorded"
    
    print("\n✅ Scorer integration test PASSED\n")


def test_database_trends():
    """Test trend computation with database."""
    print("\n" + "="*70)
    print("TEST 5: Database Trend Computation")
    print("="*70)
    
    # Create in-memory database
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute("""
        CREATE TABLE runs (
            run_id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            repo TEXT NOT NULL,
            metadata TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE file_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            file_path TEXT NOT NULL,
            language TEXT,
            doc_drift INTEGER,
            test_drift INTEGER,
            complexity INTEGER,
            naming INTEGER,
            health_score REAL,
            FOREIGN KEY (run_id) REFERENCES runs(run_id)
        )
    """)
    
    # Insert test data
    print("\n1. Inserting test data...")
    scores = [60.0, 65.0, 70.0, 75.0, 80.0, 85.0]
    for i, score in enumerate(scores):
        run_id = f'run{i+1}'
        timestamp = f'2026-01-0{i+1}T00:00:00Z'
        
        cursor.execute(
            "INSERT INTO runs (run_id, timestamp, repo) VALUES (?, ?, ?)",
            (run_id, timestamp, 'test')
        )
        cursor.execute(
            "INSERT INTO file_scores (run_id, file_path, health_score) VALUES (?, ?, ?)",
            (run_id, 'app/test.py', score)
        )
    
    conn.commit()
    print(f"   ✓ Inserted {len(scores)} data points")
    
    # Compute trends
    print("\n2. Computing trends...")
    trends = compute_trends('app/test.py', conn, n=6)
    print(f"   ✓ Growth rate: {trends['growth_rate']}")
    print(f"   ✓ Trend direction: {trends['trend_direction']}")
    print(f"   ✓ Score change: {trends['score_change']}")
    print(f"   ✓ Sparkline data: {trends['last_n_scores']}")
    
    assert trends['trend_direction'] == 'improving', "Should detect improving trend"
    assert len(trends['last_n_scores']) == 6, "Should return 6 scores"
    assert trends['score_change'] == 25.0, "Score change should be 25.0"
    
    conn.close()
    print("\n✅ Database trends test PASSED\n")


def test_full_integration():
    """Test full integration of all features."""
    print("\n" + "="*70)
    print("TEST 6: Full Integration Test")
    print("="*70)
    
    # 1. Build baseline
    print("\n1. Building baseline...")
    baseline = build_baseline('.')
    print(f"   ✓ Baseline: {baseline['total_files']} files, {baseline['docstring_coverage_pct']}% docs")
    
    # 2. Set baseline in analyzer
    print("\n2. Setting baseline in analyzer...")
    set_baseline('.')
    print("   ✓ Baseline loaded")
    
    # 3. Create sample analysis with baseline context
    print("\n3. Creating sample analysis...")
    analysis = {
        'file_path': 'app/test.py',
        'documentation_drift_score': 75,
        'test_drift_score': 70,
        'complexity_growth_score': 80,
        'naming_consistency_score': 85
    }
    
    # 4. Calculate health score with trend adjustment
    print("\n4. Calculating health score with trends...")
    trend_data = {'score_change': -12.0, 'trend_direction': 'declining'}
    penalty = compute_trend_adjustment(trend_data)
    result = calculate_health_score(analysis, trend_adjustment=penalty)
    
    print(f"   ✓ Base score calculation: {result['health_score']}")
    print(f"   ✓ Trend penalty: {penalty} points")
    print(f"   ✓ Status: {result['status']}")
    
    assert 'health_score' in result
    assert 'status' in result
    assert 'trend_penalty' in result
    
    print("\n✅ Full integration test PASSED\n")


def main():
    """Run all integration tests."""
    print("\n" + "="*70)
    print("DRIFTGUARD TRENDS & BASELINE INTEGRATION TESTS")
    print("="*70)
    
    try:
        test_baseline_integration()
        test_trend_detection()
        test_trend_adjustment()
        test_scorer_with_trends()
        test_database_trends()
        test_full_integration()
        
        print("\n" + "="*70)
        print("✅ ALL INTEGRATION TESTS PASSED!")
        print("="*70 + "\n")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}\n")
        raise
    except Exception as e:
        print(f"\n❌ ERROR: {e}\n")
        raise


if __name__ == '__main__':
    main()


# Made with Bob