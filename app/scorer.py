"""scorer.py

Convert bob_analyzer decay metrics into a weighted health score and status labels.
Also generates per-file rankings and aggregate statistics.
"""
from typing import List, Dict, Optional
from datetime import datetime, timezone
from app.config import Config
from app.models import ScoredFile, RepoSummary, DriftReport


def calculate_health_score(analysis: Dict, trend_adjustment: float = 0.0) -> Dict:
    """Calculate weighted health score from 4 decay dimensions.
    
    Args:
        analysis: dict with documentation_drift_score, test_drift_score,
                  complexity_growth_score, naming_consistency_score (0-100)
        trend_adjustment: penalty to apply based on declining trends (0-15 points)
    
    Returns:
        Same dict with added fields: health_score, status, status_emoji, trend_penalty
    """
    # Extract dimension scores, default to 50 if missing
    doc_score = analysis.get('documentation_drift_score', 50)
    test_score = analysis.get('test_drift_score', 50)
    complexity_score = analysis.get('complexity_growth_score', 50)
    naming_score = analysis.get('naming_consistency_score', 50)
    
    # Weighted average
    base_health_score = int(
        doc_score * Config.WEIGHT_DOCUMENTATION +
        test_score * Config.WEIGHT_TEST_COVERAGE +
        complexity_score * Config.WEIGHT_COMPLEXITY +
        naming_score * Config.WEIGHT_NAMING
    )
    
    # Apply trend adjustment (penalty for declining files)
    health_score = max(0, base_health_score - int(trend_adjustment))
    
    # Determine status based on thresholds
    if health_score < Config.SCORE_CRITICAL_THRESHOLD:
        status = "CRITICAL"
    elif health_score < Config.SCORE_AT_RISK_THRESHOLD:
        status = "AT_RISK"
    elif health_score < Config.SCORE_WATCH_THRESHOLD:
        status = "WATCH"
    else:
        status = "HEALTHY"
    
    status_emoji = Config.STATUS_EMOJI.get(status, "❓")
    
    # Add to analysis
    analysis['health_score'] = health_score
    analysis['status'] = status
    analysis['status_emoji'] = status_emoji
    analysis['trend_penalty'] = trend_adjustment
    
    return analysis


def score_all_files(analyses: List[Dict]) -> List[ScoredFile]:
    """Apply health score calculation to all files and sort by score (worst first).
    
    Args:
        analyses: list of analysis dicts from bob_analyzer.batch_analyze()
    
    Returns:
        List of ScoredFile dicts sorted ascending by health_score (critical first)
    """
    scored = []
    for analysis in analyses:
        scored_file = calculate_health_score(analysis.copy())
        scored.append(scored_file)
    
    # Sort by health_score ascending (worst files first)
    scored.sort(key=lambda f: f.get('health_score', 100))
    return scored


def generate_summary(scored_files: List[ScoredFile]) -> RepoSummary:
    """Generate aggregate statistics for all files.
    
    Args:
        scored_files: list of ScoredFile dicts (already scored)
    
    Returns:
        RepoSummary dict with counts by status and averages
    """
    if not scored_files:
        return {
            'total_files': 0,
            'critical_count': 0,
            'at_risk_count': 0,
            'watch_count': 0,
            'healthy_count': 0,
            'average_health_score': 0.0,
            'worst_file': None,
            'best_file': None,
        }
    
    critical = sum(1 for f in scored_files if f.get('status') == 'CRITICAL')
    at_risk = sum(1 for f in scored_files if f.get('status') == 'AT_RISK')
    watch = sum(1 for f in scored_files if f.get('status') == 'WATCH')
    healthy = sum(1 for f in scored_files if f.get('status') == 'HEALTHY')
    
    avg_score = sum(f.get('health_score', 50) for f in scored_files) / len(scored_files)
    
    worst = scored_files[0] if scored_files else None
    best = scored_files[-1] if scored_files else None
    
    return {
        'total_files': len(scored_files),
        'critical_count': critical,
        'at_risk_count': at_risk,
        'watch_count': watch,
        'healthy_count': healthy,
        'average_health_score': round(avg_score, 2),
        'worst_file': worst.get('file_path') if worst else None,
        'best_file': best.get('file_path') if best else None,
    }
