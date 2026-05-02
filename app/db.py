"""db.py

SQLite persistence layer for DriftGuard reports and file trends.
"""
import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime, timezone


DEFAULT_DB_PATH = "data/driftguard.db"


def initialize_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """Initialize SQLite database with required tables.
    
    Creates tables if they don't exist:
    - runs: stores metadata for each analysis run
    - file_scores: stores per-file scores for each run
    
    Args:
        db_path: path to SQLite database file (default: data/driftguard.db)
    """
    # Ensure parent directory exists
    db_file = Path(db_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create runs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            repo TEXT NOT NULL,
            metadata TEXT
        )
    """)
    
    # Create file_scores table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS file_scores (
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
    
    # Create index for faster trend queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_file_scores_file_path 
        ON file_scores(file_path)
    """)
    
    conn.commit()
    conn.close()


def save_run(report: dict, db_path: str = DEFAULT_DB_PATH) -> str:
    """Save a DriftReport to the database.
    
    Inserts a run record and all associated file_scores.
    
    Args:
        report: DriftReport dict from report_generator.generate_report()
        db_path: path to SQLite database file
    
    Returns:
        run_id: unique identifier for this run (ISO timestamp)
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Generate run_id from analyzed_at timestamp
    run_id = report.get('analyzed_at', datetime.now(timezone.utc).isoformat())
    timestamp = run_id
    repo = report.get('repo', 'unknown')
    
    # Store summary and analysis window in metadata
    metadata = {
        'analysis_window_days': report.get('analysis_window_days', 0),
        'summary': report.get('summary', {})
    }
    metadata_json = json.dumps(metadata)
    
    # Insert run record
    cursor.execute("""
        INSERT INTO runs (run_id, timestamp, repo, metadata)
        VALUES (?, ?, ?, ?)
    """, (run_id, timestamp, repo, metadata_json))
    
    # Insert all file scores
    files = report.get('files', [])
    for file_data in files:
        cursor.execute("""
            INSERT INTO file_scores (
                run_id, file_path, language, 
                doc_drift, test_drift, complexity, naming,
                health_score
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_id,
            file_data.get('file_path', ''),
            file_data.get('language', ''),
            file_data.get('documentation_drift_score', 0),
            file_data.get('test_drift_score', 0),
            file_data.get('complexity_growth_score', 0),
            file_data.get('naming_consistency_score', 0),
            file_data.get('health_score', 0.0)
        ))
    
    conn.commit()
    conn.close()
    
    return run_id


def get_file_trends(file_path: str, db_path: str = DEFAULT_DB_PATH) -> List[Dict]:
    """Get historical trend data for a specific file.
    
    Returns all runs where this file was analyzed, sorted by timestamp ascending.
    
    Args:
        file_path: relative path to the file (e.g., "app/main.py")
        db_path: path to SQLite database file
    
    Returns:
        List of dicts with keys: run_id, timestamp, health_score, 
        doc_drift, test_drift, complexity, naming
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            fs.run_id,
            r.timestamp,
            fs.health_score,
            fs.doc_drift,
            fs.test_drift,
            fs.complexity,
            fs.naming
        FROM file_scores fs
        JOIN runs r ON fs.run_id = r.run_id
        WHERE fs.file_path = ?
        ORDER BY r.timestamp ASC
    """, (file_path,))
    
    rows = cursor.fetchall()
    conn.close()
    
    # Convert Row objects to dicts
    trends = []
    for row in rows:
        trends.append({
            'run_id': row['run_id'],
            'timestamp': row['timestamp'],
            'health_score': row['health_score'],
            'doc_drift': row['doc_drift'],
            'test_drift': row['test_drift'],
            'complexity': row['complexity'],
            'naming': row['naming']
        })
    
    return trends


def get_latest_run(db_path: str = DEFAULT_DB_PATH) -> Optional[Dict]:
    """Get the most recent analysis run.
    
    Args:
        db_path: path to SQLite database file
    
    Returns:
        Dict with run metadata or None if no runs exist
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT run_id, timestamp, repo, metadata
        FROM runs
        ORDER BY timestamp DESC
        LIMIT 1
    """)
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            'run_id': row['run_id'],
            'timestamp': row['timestamp'],
            'repo': row['repo'],
            'metadata': json.loads(row['metadata']) if row['metadata'] else {}
        }
    return None


def get_all_runs(db_path: str = DEFAULT_DB_PATH) -> List[Dict]:
    """Get all analysis runs, sorted by timestamp descending.
    
    Args:
        db_path: path to SQLite database file
    
    Returns:
        List of dicts with run metadata
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT run_id, timestamp, repo, metadata
        FROM runs
        ORDER BY timestamp DESC
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    runs = []
    for row in rows:
        runs.append({
            'run_id': row['run_id'],
            'timestamp': row['timestamp'],
            'repo': row['repo'],
            'metadata': json.loads(row['metadata']) if row['metadata'] else {}
        })
    
    return runs

# Made with Bob
