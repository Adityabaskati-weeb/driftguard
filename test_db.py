"""test_db.py

Unit tests for database persistence layer.
"""
import os
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app import db


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    # Initialize the database
    db.initialize_db(path)
    
    yield path
    
    # Cleanup
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def sample_report():
    """Create a sample DriftReport for testing."""
    return {
        'repo': '/test/repo',
        'analysis_window_days': 30,
        'analyzed_at': '2026-05-02T12:00:00+00:00',
        'files': [
            {
                'file_path': 'app/main.py',
                'language': 'python',
                'total_commits': 5,
                'documentation_drift_score': 85,
                'test_drift_score': 70,
                'complexity_growth_score': 90,
                'naming_consistency_score': 95,
                'health_score': 85.0,
                'status': 'HEALTHY',
                'status_emoji': '🟢',
                'decay_summary': 'File is in good shape',
                'top_risk': 'Test coverage could be improved',
                'recommendation': 'Add more unit tests'
            },
            {
                'file_path': 'app/utils.py',
                'language': 'python',
                'total_commits': 3,
                'documentation_drift_score': 60,
                'test_drift_score': 50,
                'complexity_growth_score': 70,
                'naming_consistency_score': 80,
                'health_score': 65.0,
                'status': 'WATCH',
                'status_emoji': '🟡',
                'decay_summary': 'Some concerns detected',
                'top_risk': 'Documentation is outdated',
                'recommendation': 'Update docstrings'
            },
            {
                'file_path': 'app/auth.py',
                'language': 'python',
                'total_commits': 8,
                'documentation_drift_score': 40,
                'test_drift_score': 30,
                'complexity_growth_score': 45,
                'naming_consistency_score': 55,
                'health_score': 42.5,
                'status': 'AT_RISK',
                'status_emoji': '🟠',
                'decay_summary': 'Significant decay detected',
                'top_risk': 'High complexity with poor test coverage',
                'recommendation': 'Refactor and add tests'
            }
        ],
        'summary': {
            'total_files': 3,
            'critical_count': 0,
            'at_risk_count': 1,
            'watch_count': 1,
            'healthy_count': 1,
            'average_health_score': 64.17,
            'worst_file': 'app/auth.py',
            'best_file': 'app/main.py'
        }
    }


def test_initialize_db(temp_db):
    """Test database initialization creates required tables."""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    
    # Check runs table exists
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='runs'
    """)
    assert cursor.fetchone() is not None
    
    # Check file_scores table exists
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='file_scores'
    """)
    assert cursor.fetchone() is not None
    
    # Check index exists
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='index' AND name='idx_file_scores_file_path'
    """)
    assert cursor.fetchone() is not None
    
    conn.close()


def test_save_run(temp_db, sample_report):
    """Test saving a report to the database."""
    run_id = db.save_run(sample_report, temp_db)
    
    # Verify run_id is returned
    assert run_id == sample_report['analyzed_at']
    
    # Verify run record was created
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
    run = cursor.fetchone()
    assert run is not None
    assert run[2] == '/test/repo'  # repo column
    
    # Verify file_scores were created
    cursor.execute("SELECT COUNT(*) FROM file_scores WHERE run_id = ?", (run_id,))
    count = cursor.fetchone()[0]
    assert count == 3  # 3 files in sample report
    
    # Verify specific file data
    cursor.execute("""
        SELECT file_path, health_score, doc_drift, test_drift, complexity, naming
        FROM file_scores 
        WHERE run_id = ? AND file_path = 'app/main.py'
    """, (run_id,))
    file_data = cursor.fetchone()
    assert file_data is not None
    assert file_data[0] == 'app/main.py'
    assert file_data[1] == 85.0  # health_score
    assert file_data[2] == 85     # doc_drift
    assert file_data[3] == 70     # test_drift
    assert file_data[4] == 90     # complexity
    assert file_data[5] == 95     # naming
    
    conn.close()


def test_get_file_trends(temp_db, sample_report):
    """Test retrieving file trends across multiple runs."""
    # Save first run
    run_id_1 = db.save_run(sample_report, temp_db)
    
    # Modify report for second run
    sample_report['analyzed_at'] = '2026-05-03T12:00:00+00:00'
    sample_report['files'][0]['health_score'] = 90.0
    sample_report['files'][0]['documentation_drift_score'] = 90
    run_id_2 = db.save_run(sample_report, temp_db)
    
    # Modify report for third run
    sample_report['analyzed_at'] = '2026-05-04T12:00:00+00:00'
    sample_report['files'][0]['health_score'] = 88.0
    sample_report['files'][0]['test_drift_score'] = 75
    run_id_3 = db.save_run(sample_report, temp_db)
    
    # Get trends for app/main.py
    trends = db.get_file_trends('app/main.py', temp_db)
    
    # Verify we got 3 data points
    assert len(trends) == 3
    
    # Verify they're sorted by timestamp ascending
    assert trends[0]['run_id'] == run_id_1
    assert trends[1]['run_id'] == run_id_2
    assert trends[2]['run_id'] == run_id_3
    
    # Verify health scores show progression
    assert trends[0]['health_score'] == 85.0
    assert trends[1]['health_score'] == 90.0
    assert trends[2]['health_score'] == 88.0
    
    # Verify dimension scores are included
    assert trends[0]['doc_drift'] == 85
    assert trends[1]['doc_drift'] == 90
    assert trends[0]['test_drift'] == 70
    assert trends[2]['test_drift'] == 75


def test_get_file_trends_no_data(temp_db):
    """Test get_file_trends returns empty list for non-existent file."""
    trends = db.get_file_trends('nonexistent/file.py', temp_db)
    assert trends == []


def test_get_latest_run(temp_db, sample_report):
    """Test retrieving the most recent run."""
    # Save first run
    db.save_run(sample_report, temp_db)
    
    # Save second run (more recent)
    sample_report['analyzed_at'] = '2026-05-03T12:00:00+00:00'
    run_id_2 = db.save_run(sample_report, temp_db)
    
    # Get latest run
    latest = db.get_latest_run(temp_db)
    
    assert latest is not None
    assert latest['run_id'] == run_id_2
    assert latest['repo'] == '/test/repo'
    assert 'metadata' in latest
    assert latest['metadata']['analysis_window_days'] == 30


def test_get_latest_run_empty_db(temp_db):
    """Test get_latest_run returns None for empty database."""
    latest = db.get_latest_run(temp_db)
    assert latest is None


def test_get_all_runs(temp_db, sample_report):
    """Test retrieving all runs."""
    # Save three runs
    db.save_run(sample_report, temp_db)
    
    sample_report['analyzed_at'] = '2026-05-03T12:00:00+00:00'
    db.save_run(sample_report, temp_db)
    
    sample_report['analyzed_at'] = '2026-05-04T12:00:00+00:00'
    db.save_run(sample_report, temp_db)
    
    # Get all runs
    runs = db.get_all_runs(temp_db)
    
    assert len(runs) == 3
    # Verify they're sorted by timestamp descending (most recent first)
    assert runs[0]['timestamp'] > runs[1]['timestamp']
    assert runs[1]['timestamp'] > runs[2]['timestamp']


def test_multiple_files_same_path(temp_db, sample_report):
    """Test that multiple runs track the same file correctly."""
    # Save first run
    db.save_run(sample_report, temp_db)
    
    # Modify and save second run
    sample_report['analyzed_at'] = '2026-05-03T12:00:00+00:00'
    sample_report['files'][1]['health_score'] = 75.0  # app/utils.py improved
    db.save_run(sample_report, temp_db)
    
    # Get trends for app/utils.py
    trends = db.get_file_trends('app/utils.py', temp_db)
    
    assert len(trends) == 2
    assert trends[0]['health_score'] == 65.0
    assert trends[1]['health_score'] == 75.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

# Made with Bob
