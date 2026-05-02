"""trends.py

Trend computation and analysis for DriftGuard.
Computes growth/decay rates and detects trend directions from historical data.
"""

import sqlite3
from typing import List, Dict, Tuple, Optional
from statistics import mean, stdev


def compute_trends(file_path: str, db_conn: sqlite3.Connection, n: int = 6) -> Dict:
    """Compute trend metrics for a file from historical data.
    
    Args:
        file_path: relative path to the file
        db_conn: SQLite database connection
        n: number of most recent scores to return (default: 6 for sparkline)
    
    Returns:
        Dict with keys:
        - growth_rate: float (positive = improving, negative = declining)
        - last_n_scores: List[float] (most recent n health scores)
        - trend_direction: "improving" | "declining" | "stable"
        - score_change: float (difference between first and last score)
        - volatility: float (standard deviation of scores, 0 if < 2 points)
    """
    cursor = db_conn.cursor()
    
    # Get historical health scores for this file
    cursor.execute("""
        SELECT 
            fs.health_score,
            r.timestamp
        FROM file_scores fs
        JOIN runs r ON fs.run_id = r.run_id
        WHERE fs.file_path = ?
        ORDER BY r.timestamp ASC
    """, (file_path,))
    
    rows = cursor.fetchall()
    
    if not rows:
        return {
            'growth_rate': 0.0,
            'last_n_scores': [],
            'trend_direction': 'stable',
            'score_change': 0.0,
            'volatility': 0.0
        }
    
    # Extract scores
    all_scores = [row[0] for row in rows]
    
    # Get last N scores for sparkline
    last_n_scores = all_scores[-n:] if len(all_scores) >= n else all_scores
    
    # Calculate growth rate (simple linear approximation)
    if len(all_scores) >= 2:
        # Use first and last score to compute rate
        first_score = all_scores[0]
        last_score = all_scores[-1]
        score_change = last_score - first_score
        
        # Growth rate as change per data point
        growth_rate = score_change / len(all_scores)
    else:
        score_change = 0.0
        growth_rate = 0.0
    
    # Calculate volatility (standard deviation)
    volatility = stdev(all_scores) if len(all_scores) >= 2 else 0.0
    
    # Detect trend direction using last 3 points
    trend_direction = detect_trend_direction(all_scores[-3:] if len(all_scores) >= 3 else all_scores)
    
    return {
        'growth_rate': round(growth_rate, 2),
        'last_n_scores': [round(s, 1) for s in last_n_scores],
        'trend_direction': trend_direction,
        'score_change': round(score_change, 2),
        'volatility': round(volatility, 2)
    }


def detect_trend_direction(scores: List[float]) -> str:
    """Detect trend direction using slope heuristic on last N points.
    
    Uses a simple slope calculation on the last 3 points (or fewer if not available).
    
    Args:
        scores: List of health scores (should be last 3 points ideally)
    
    Returns:
        "improving" | "declining" | "stable"
    """
    if len(scores) < 2:
        return "stable"
    
    # Calculate simple slope using first and last point
    first = scores[0]
    last = scores[-1]
    change = last - first
    
    # Thresholds for trend detection
    IMPROVING_THRESHOLD = 5.0  # Score increased by 5+ points
    DECLINING_THRESHOLD = -5.0  # Score decreased by 5+ points
    
    if change >= IMPROVING_THRESHOLD:
        return "improving"
    elif change <= DECLINING_THRESHOLD:
        return "declining"
    else:
        return "stable"


def get_declining_files(db_conn: sqlite3.Connection, threshold: float = -10.0) -> List[Dict]:
    """Get files that have declined significantly in recent runs.
    
    Args:
        db_conn: SQLite database connection
        threshold: minimum score change to consider (negative, default: -10.0)
    
    Returns:
        List of dicts with file_path, score_change, and current_score
    """
    cursor = db_conn.cursor()
    
    # Get all unique files
    cursor.execute("SELECT DISTINCT file_path FROM file_scores")
    files = [row[0] for row in cursor.fetchall()]
    
    declining = []
    
    for file_path in files:
        # Get first and last score for this file
        cursor.execute("""
            SELECT health_score
            FROM file_scores fs
            JOIN runs r ON fs.run_id = r.run_id
            WHERE fs.file_path = ?
            ORDER BY r.timestamp ASC
        """, (file_path,))
        
        scores = [row[0] for row in cursor.fetchall()]
        
        if len(scores) >= 2:
            first_score = scores[0]
            last_score = scores[-1]
            change = last_score - first_score
            
            if change <= threshold:
                declining.append({
                    'file_path': file_path,
                    'score_change': round(change, 2),
                    'current_score': round(last_score, 2),
                    'previous_score': round(first_score, 2)
                })
    
    # Sort by score change (worst first)
    declining.sort(key=lambda x: x['score_change'])
    
    return declining


def compute_trend_adjustment(trend_data: Dict) -> float:
    """Calculate score adjustment based on trend data.
    
    Penalizes files that are declining significantly.
    
    Args:
        trend_data: output from compute_trends()
    
    Returns:
        Adjustment value to subtract from health score (0 to 15 points)
    """
    score_change = trend_data.get('score_change', 0.0)
    trend_direction = trend_data.get('trend_direction', 'stable')
    
    # No penalty for improving or stable trends
    if trend_direction in ['improving', 'stable']:
        return 0.0
    
    # Penalty for declining trends
    if score_change <= -20:
        return 15.0  # Severe decline: -15 points
    elif score_change <= -10:
        return 10.0  # Significant decline: -10 points
    elif score_change <= -5:
        return 5.0   # Moderate decline: -5 points
    else:
        return 0.0   # Minor decline: no penalty


# Made with Bob