"""scorer.py

Health score calculation for DriftGuard.
Converts Bob's 4-dimension decay scores into a weighted health score.
"""

from typing import Dict, List
from app.config import Config


def calculate_health_score(analysis: Dict) -> Dict:
    """
    Calculate weighted health score and assign status label.
    
    Args:
        analysis: Dict with Bob's 4 dimension scores (0-100 each)
    
    Returns:
        Same dict with added fields:
        - health_score: int (0-100, weighted average)
        - status: str ("CRITICAL" | "AT_RISK" | "WATCH" | "HEALTHY")
        - status_emoji: str ("🔴" | "🟠" | "🟡" | "🟢")
    """
    # Extract dimension scores
    doc_score = analysis.get('documentation_drift_score', 50)
    test_score = analysis.get('test_drift_score', 50)
    complexity_score = analysis.get('complexity_growth_score', 50)
    naming_score = analysis.get('naming_consistency_score', 50)
    
    # Calculate weighted average
    health_score = (
        doc_score * Config.WEIGHT_DOCUMENTATION +
        test_score * Config.WEIGHT_TEST_COVERAGE +
        complexity_score * Config.WEIGHT_COMPLEXITY +
        naming_score * Config.WEIGHT_NAMING
    )
    
    # Round to integer
    health_score = int(round(health_score))
    
    # Assign status label based on thresholds
    if health_score < Config.SCORE_CRITICAL_THRESHOLD:
        status = "CRITICAL"
    elif health_score < Config.SCORE_AT_RISK_THRESHOLD:
        status = "AT_RISK"
    elif health_score < Config.SCORE_WATCH_THRESHOLD:
        status = "WATCH"
    else:
        status = "HEALTHY"
    
    # Get emoji for status
    status_emoji = Config.STATUS_EMOJI.get(status, "⚪")
    
    # Add to analysis dict
    result = {
        **analysis,
        'health_score': health_score,
        'status': status,
        'status_emoji': status_emoji
    }
    
    return result


def score_all_files(analyses: List[Dict]) -> List[Dict]:
    """
    Apply health scoring to all analyzed files and sort by score.
    
    Args:
        analyses: List of file analysis dicts from bob_analyzer
    
    Returns:
        List of scored files, sorted by health_score ascending (worst first)
    """
    scored_files = []
    
    for analysis in analyses:
        scored = calculate_health_score(analysis)
        scored_files.append(scored)
    
    # Sort by health score ascending (worst files first)
    scored_files.sort(key=lambda x: x['health_score'])
    
    return scored_files


def generate_summary(scored_files: List[Dict]) -> Dict:
    """
    Generate aggregate statistics for a set of scored files.
    
    Args:
        scored_files: List of scored file dicts
    
    Returns:
        Dict with summary statistics:
        - total_files: int
        - critical_count: int
        - at_risk_count: int
        - watch_count: int
        - healthy_count: int
        - average_health_score: float
        - worst_file: str (file_path)
        - best_file: str (file_path)
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
            'best_file': None
        }
    
    # Count by status
    status_counts = {
        'CRITICAL': 0,
        'AT_RISK': 0,
        'WATCH': 0,
        'HEALTHY': 0
    }
    
    total_score = 0
    
    for file in scored_files:
        status = file.get('status', 'WATCH')
        if status in status_counts:
            status_counts[status] += 1
        total_score += file.get('health_score', 50)
    
    # Calculate average
    avg_score = total_score / len(scored_files)
    
    # Find worst and best files
    worst_file = scored_files[0]['file_path']  # Already sorted, first is worst
    best_file = scored_files[-1]['file_path']  # Last is best
    
    return {
        'total_files': len(scored_files),
        'critical_count': status_counts['CRITICAL'],
        'at_risk_count': status_counts['AT_RISK'],
        'watch_count': status_counts['WATCH'],
        'healthy_count': status_counts['HEALTHY'],
        'average_health_score': round(avg_score, 1),
        'worst_file': worst_file,
        'best_file': best_file
    }


def print_summary_table(scored_files: List[Dict]) -> None:
    """
    Print a formatted summary table to terminal.
    
    Args:
        scored_files: List of scored file dicts
    """
    if not scored_files:
        print("No files to display.")
        return
    
    # Print header
    print("\n" + "=" * 100)
    print(f"{'File':<50} {'Score':<8} {'Status':<12} {'Top Risk':<30}")
    print("=" * 100)
    
    # Print each file
    for file in scored_files:
        filename = file['file_path']
        if len(filename) > 48:
            filename = "..." + filename[-45:]
        
        score = file['health_score']
        status = f"{file['status_emoji']} {file['status']}"
        top_risk = file.get('top_risk', 'N/A')
        
        # Truncate top_risk if too long
        if len(top_risk) > 28:
            top_risk = top_risk[:25] + "..."
        
        print(f"{filename:<50} {score:<8} {status:<12} {top_risk:<30}")
    
    print("=" * 100)
    
    # Print summary stats
    summary = generate_summary(scored_files)
    print(f"\n📊 Summary:")
    print(f"   Total files: {summary['total_files']}")
    print(f"   🔴 Critical: {summary['critical_count']}")
    print(f"   🟠 At Risk: {summary['at_risk_count']}")
    print(f"   🟡 Watch: {summary['watch_count']}")
    print(f"   🟢 Healthy: {summary['healthy_count']}")
    print(f"   Average health score: {summary['average_health_score']:.1f}/100")
    print(f"   Worst file: {summary['worst_file']}")
    print(f"   Best file: {summary['best_file']}")
    print()


def test_scorer():
    """
    Test function to verify scoring logic.
    """
    import sys
    import io
    
    # Set UTF-8 encoding for Windows console
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("[TEST] Testing scorer module...")
    print("-" * 60)
    
    # Sample test data
    test_analyses = [
        {
            'file_path': 'app/critical.py',
            'documentation_drift_score': 20,
            'test_drift_score': 15,
            'complexity_growth_score': 30,
            'naming_consistency_score': 40,
            'decay_summary': 'Severe decay detected',
            'top_risk': 'No documentation updates',
            'recommendation': 'Add docstrings'
        },
        {
            'file_path': 'app/healthy.py',
            'documentation_drift_score': 90,
            'test_drift_score': 85,
            'complexity_growth_score': 88,
            'naming_consistency_score': 92,
            'decay_summary': 'Well maintained',
            'top_risk': 'None',
            'recommendation': 'Keep up the good work'
        },
        {
            'file_path': 'app/at_risk.py',
            'documentation_drift_score': 45,
            'test_drift_score': 50,
            'complexity_growth_score': 55,
            'naming_consistency_score': 48,
            'decay_summary': 'Moderate decay',
            'top_risk': 'Test coverage declining',
            'recommendation': 'Update tests'
        }
    ]
    
    # Score all files
    scored = score_all_files(test_analyses)
    
    print("\n[RESULT] Scored files:")
    for file in scored:
        print(f"\n  {file['file_path']}")
        print(f"    Health Score: {file['health_score']}/100")
        print(f"    Status: {file['status_emoji']} {file['status']}")
        print(f"    Dimensions: Doc={file['documentation_drift_score']}, "
              f"Test={file['test_drift_score']}, "
              f"Complex={file['complexity_growth_score']}, "
              f"Naming={file['naming_consistency_score']}")
    
    # Generate summary
    summary = generate_summary(scored)
    print("\n[SUMMARY]")
    print(f"  Total files: {summary['total_files']}")
    print(f"  Critical: {summary['critical_count']}")
    print(f"  At Risk: {summary['at_risk_count']}")
    print(f"  Watch: {summary['watch_count']}")
    print(f"  Healthy: {summary['healthy_count']}")
    print(f"  Average: {summary['average_health_score']:.1f}/100")
    print(f"  Worst: {summary['worst_file']}")
    print(f"  Best: {summary['best_file']}")
    
    print("\n" + "=" * 60)
    print("[TEST] Complete")


if __name__ == '__main__':
    test_scorer()

# Made with Bob