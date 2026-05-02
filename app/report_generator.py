"""report_generator.py

JSON report generation and persistence for DriftGuard.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


def generate_report(
    scored_files: List[Dict],
    repo_path: str,
    analysis_days: int,
    metadata: Optional[Dict] = None
) -> Dict:
    """
    Generate a complete DriftGuard report from scored files.
    
    Args:
        scored_files: List of scored file dicts from scorer
        repo_path: Path to the analyzed repository
        analysis_days: Number of days analyzed
        metadata: Optional additional metadata
    
    Returns:
        Complete DriftReport dict ready for JSON serialization
    """
    from app.scorer import generate_summary
    
    # Generate summary statistics
    summary = generate_summary(scored_files)
    
    # Build report
    from datetime import timezone
    report = {
        'repo': repo_path,
        'analysis_window_days': analysis_days,
        'analyzed_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'files': scored_files,
        'summary': summary
    }
    
    # Add optional metadata
    if metadata:
        report['metadata'] = metadata
    
    return report


def save_report(report: Dict, output_path: str) -> None:
    """
    Save report as JSON file.
    
    Args:
        report: DriftReport dict
        output_path: Path to save JSON file
    """
    output_file = Path(output_path)
    
    # Create parent directory if it doesn't exist
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Write JSON with pretty formatting
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Report saved to: {output_path}")


def load_report(input_path: str) -> Dict:
    """
    Load report from JSON file.
    
    Args:
        input_path: Path to JSON report file
    
    Returns:
        DriftReport dict
    
    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file is not valid JSON
    """
    input_file = Path(input_path)
    
    if not input_file.exists():
        raise FileNotFoundError(f"Report file not found: {input_path}")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        report = json.load(f)
    
    return report


def get_latest_report(output_dir: str) -> Optional[Dict]:
    """
    Find and load the most recent report from output directory.
    
    Args:
        output_dir: Directory containing report files
    
    Returns:
        DriftReport dict or None if no reports found
    """
    output_path = Path(output_dir)
    
    if not output_path.exists():
        return None
    
    # Find all JSON files matching report pattern
    report_files = list(output_path.glob('report_*.json'))
    
    if not report_files:
        return None
    
    # Get most recent by modification time
    latest_file = max(report_files, key=lambda p: p.stat().st_mtime)
    
    try:
        return load_report(str(latest_file))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def format_report_summary(report: Dict) -> str:
    """
    Format report summary as human-readable text.
    
    Args:
        report: DriftReport dict
    
    Returns:
        Formatted summary string
    """
    summary = report.get('summary', {})
    
    lines = [
        "",
        "=" * 80,
        "📊 DRIFTGUARD REPORT SUMMARY",
        "=" * 80,
        f"Repository: {report.get('repo', 'Unknown')}",
        f"Analysis Window: {report.get('analysis_window_days', 0)} days",
        f"Analyzed At: {report.get('analyzed_at', 'Unknown')}",
        "",
        f"Total Files Analyzed: {summary.get('total_files', 0)}",
        f"  🔴 Critical: {summary.get('critical_count', 0)}",
        f"  🟠 At Risk: {summary.get('at_risk_count', 0)}",
        f"  🟡 Watch: {summary.get('watch_count', 0)}",
        f"  🟢 Healthy: {summary.get('healthy_count', 0)}",
        "",
        f"Average Health Score: {summary.get('average_health_score', 0):.1f}/100",
        f"Worst File: {summary.get('worst_file', 'N/A')}",
        f"Best File: {summary.get('best_file', 'N/A')}",
        "=" * 80,
        ""
    ]
    
    return "\n".join(lines)


def export_markdown(report: Dict, output_path: str) -> None:
    """
    Export report as Markdown file.
    
    Args:
        report: DriftReport dict
        output_path: Path to save Markdown file
    """
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    summary = report.get('summary', {})
    files = report.get('files', [])
    
    # Build markdown content
    lines = [
        f"# DriftGuard Report",
        f"",
        f"**Repository:** {report.get('repo', 'Unknown')}  ",
        f"**Analysis Window:** {report.get('analysis_window_days', 0)} days  ",
        f"**Analyzed At:** {report.get('analyzed_at', 'Unknown')}  ",
        f"",
        f"## Summary",
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total Files | {summary.get('total_files', 0)} |",
        f"| 🔴 Critical | {summary.get('critical_count', 0)} |",
        f"| 🟠 At Risk | {summary.get('at_risk_count', 0)} |",
        f"| 🟡 Watch | {summary.get('watch_count', 0)} |",
        f"| 🟢 Healthy | {summary.get('healthy_count', 0)} |",
        f"| Average Health Score | {summary.get('average_health_score', 0):.1f}/100 |",
        f"",
        f"**Worst File:** `{summary.get('worst_file', 'N/A')}`  ",
        f"**Best File:** `{summary.get('best_file', 'N/A')}`  ",
        f"",
        f"## Files Requiring Attention",
        f""
    ]
    
    # Add critical and at-risk files
    critical_files = [f for f in files if f.get('status') == 'CRITICAL']
    at_risk_files = [f for f in files if f.get('status') == 'AT_RISK']
    
    if critical_files:
        lines.append("### 🔴 Critical Files")
        lines.append("")
        for file in critical_files:
            lines.extend([
                f"#### `{file['file_path']}`",
                f"",
                f"**Health Score:** {file['health_score']}/100  ",
                f"**Top Risk:** {file.get('top_risk', 'N/A')}  ",
                f"**Recommendation:** {file.get('recommendation', 'N/A')}  ",
                f"",
                f"**Dimension Scores:**",
                f"- Documentation Drift: {file.get('documentation_drift_score', 0)}/100",
                f"- Test Drift: {file.get('test_drift_score', 0)}/100",
                f"- Complexity Growth: {file.get('complexity_growth_score', 0)}/100",
                f"- Naming Consistency: {file.get('naming_consistency_score', 0)}/100",
                f"",
                f"**Analysis:** {file.get('decay_summary', 'N/A')}",
                f"",
                f"---",
                f""
            ])
    
    if at_risk_files:
        lines.append("### 🟠 At Risk Files")
        lines.append("")
        for file in at_risk_files:
            lines.extend([
                f"#### `{file['file_path']}`",
                f"",
                f"**Health Score:** {file['health_score']}/100  ",
                f"**Top Risk:** {file.get('top_risk', 'N/A')}  ",
                f"**Recommendation:** {file.get('recommendation', 'N/A')}  ",
                f"",
                f"---",
                f""
            ])
    
    # Write to file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    print(f"✅ Markdown report saved to: {output_path}")


def test_report_generator():
    """
    Test function to verify report generation.
    """
    import sys
    import io
    
    # Set UTF-8 encoding for Windows console
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("[TEST] Testing report generator...")
    print("-" * 60)
    
    # Sample scored files
    test_files = [
        {
            'file_path': 'app/critical.py',
            'language': 'python',
            'total_commits': 5,
            'health_score': 35,
            'status': 'CRITICAL',
            'status_emoji': '🔴',
            'documentation_drift_score': 20,
            'test_drift_score': 30,
            'complexity_growth_score': 40,
            'naming_consistency_score': 50,
            'decay_summary': 'Severe decay detected',
            'top_risk': 'No documentation updates',
            'recommendation': 'Add docstrings'
        },
        {
            'file_path': 'app/healthy.py',
            'language': 'python',
            'total_commits': 2,
            'health_score': 88,
            'status': 'HEALTHY',
            'status_emoji': '🟢',
            'documentation_drift_score': 90,
            'test_drift_score': 85,
            'complexity_growth_score': 88,
            'naming_consistency_score': 92,
            'decay_summary': 'Well maintained',
            'top_risk': 'None',
            'recommendation': 'Keep up the good work'
        }
    ]
    
    # Generate report
    report = generate_report(
        scored_files=test_files,
        repo_path='./test-repo',
        analysis_days=30
    )
    
    print("\n[RESULT] Generated report:")
    print(f"  Repo: {report['repo']}")
    print(f"  Days: {report['analysis_window_days']}")
    print(f"  Files: {len(report['files'])}")
    print(f"  Summary: {report['summary']}")
    
    # Test summary formatting
    print("\n[FORMATTED SUMMARY]")
    print(format_report_summary(report))
    
    print("=" * 60)
    print("[TEST] Complete")


if __name__ == '__main__':
    test_report_generator()

# Made with Bob