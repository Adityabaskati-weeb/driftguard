"""db.py

SQLite persistence layer for DriftGuard reports and file trends.
"""
import sqlite3
import json
import hashlib
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime, timezone, timedelta


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
    
    # Create analysis_cache table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS analysis_cache (
            cache_key TEXT PRIMARY KEY,
            file_path TEXT NOT NULL,
            diff_hash TEXT NOT NULL,
            language TEXT,
            analysis_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    
    # Create index for cache lookups by file_path
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_cache_file_path
        ON analysis_cache(file_path)
    """)
    
    # Create index for cache expiry queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_cache_created_at
        ON analysis_cache(created_at)
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


# ============================================================================
# ANALYSIS CACHE FUNCTIONS
# ============================================================================

def compute_cache_key(file_path: str, diff_hash: str) -> str:
    """Compute cache key from file path and diff hash.
    
    Args:
        file_path: relative path to the file
        diff_hash: hash of the diff content
    
    Returns:
        SHA256 hash as hex string
    """
    key_input = f"{file_path}:{diff_hash}"
    return hashlib.sha256(key_input.encode('utf-8')).hexdigest()


def compute_diff_hash(diff_text: str) -> str:
    """Compute SHA256 hash of diff text.
    
    Args:
        diff_text: the diff content to hash
    
    Returns:
        SHA256 hash as hex string
    """
    return hashlib.sha256(diff_text.encode('utf-8')).hexdigest()


def get_cached_analysis(file_path: str, diff_hash: str,
                       ttl_hours: Optional[int] = None,
                       db_path: str = DEFAULT_DB_PATH) -> Optional[Dict]:
    """Retrieve cached analysis result if available and not expired.
    
    Args:
        file_path: relative path to the file
        diff_hash: hash of the diff content
        ttl_hours: time-to-live in hours (None = no expiry)
        db_path: path to SQLite database file
    
    Returns:
        Cached analysis dict or None if not found/expired
    """
    cache_key = compute_cache_key(file_path, diff_hash)
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT analysis_json, created_at
        FROM analysis_cache
        WHERE cache_key = ?
    """, (cache_key,))
    
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return None
    
    # Check TTL if specified
    if ttl_hours is not None:
        created_at = datetime.fromisoformat(row['created_at'])
        now = datetime.now(timezone.utc)
        age_hours = (now - created_at).total_seconds() / 3600
        
        if age_hours > ttl_hours:
            # Cache expired
            return None
    
    # Return cached analysis
    return json.loads(row['analysis_json'])


def save_cached_analysis(file_path: str, diff_hash: str, language: str,
                        analysis_result: Dict,
                        db_path: str = DEFAULT_DB_PATH) -> None:
    """Save analysis result to cache.
    
    Args:
        file_path: relative path to the file
        diff_hash: hash of the diff content
        language: programming language
        analysis_result: the analysis result dict to cache
        db_path: path to SQLite database file
    """
    cache_key = compute_cache_key(file_path, diff_hash)
    analysis_json = json.dumps(analysis_result)
    created_at = datetime.now(timezone.utc).isoformat()
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Use INSERT OR REPLACE to handle duplicates
    cursor.execute("""
        INSERT OR REPLACE INTO analysis_cache
        (cache_key, file_path, diff_hash, language, analysis_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (cache_key, file_path, diff_hash, language, analysis_json, created_at))
    
    conn.commit()
    conn.close()


def clear_expired_cache(ttl_hours: int, db_path: str = DEFAULT_DB_PATH) -> int:
    """Remove expired cache entries.
    
    Args:
        ttl_hours: time-to-live in hours
        db_path: path to SQLite database file
    
    Returns:
        Number of entries deleted
    """
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=ttl_hours)
    cutoff_iso = cutoff_time.isoformat()
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        DELETE FROM analysis_cache
        WHERE created_at < ?
    """, (cutoff_iso,))
    
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()
    
    return deleted_count


def get_cache_stats(db_path: str = DEFAULT_DB_PATH) -> Dict:
    """Get cache statistics.
    
    Args:
        db_path: path to SQLite database file
    
    Returns:
        Dict with cache statistics
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Total entries
    cursor.execute("SELECT COUNT(*) FROM analysis_cache")
    total_entries = cursor.fetchone()[0]
    
    # Entries by language
    cursor.execute("""
        SELECT language, COUNT(*) as count
        FROM analysis_cache
        GROUP BY language
        ORDER BY count DESC
    """)
    by_language = {row[0]: row[1] for row in cursor.fetchall()}
    
    # Oldest and newest entries
    cursor.execute("""
        SELECT MIN(created_at) as oldest, MAX(created_at) as newest
        FROM analysis_cache
    """)
    row = cursor.fetchone()
    oldest = row[0] if row[0] else None
    newest = row[1] if row[1] else None
    
    conn.close()
    
    return {
        'total_entries': total_entries,
        'by_language': by_language,
        'oldest_entry': oldest,
        'newest_entry': newest
    }

# Made with Bob
