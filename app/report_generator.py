"""report_generator.py

Build JSON reports from scored file data and save to disk.
"""
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict

from app.config import Config, get_output_report_path
from app.models import DriftReport
from app.scorer import generate_summary
from app import db


# Initialize database on module import
db.initialize_db()


def generate_report(
    repo_path: str,
    days: int,
    scored_files: List[Dict],
) -> DriftReport:
    """Generate final DriftReport from scored files.
    
    Args:
        repo_path: path to the repository
        days: analysis window in days
        scored_files: list of ScoredFile dicts from scorer.score_all_files()
    
    Returns:
        DriftReport dict ready for JSON serialization
    """
    summary = generate_summary(scored_files)
    
    # Generate timestamp with microseconds for uniqueness
    timestamp = datetime.now(timezone.utc).isoformat(timespec='microseconds')
    
    report: DriftReport = {
        'repo': str(repo_path),
        'analysis_window_days': days,
        'analyzed_at': timestamp,
        'files': scored_files,
        'summary': summary,
    }
    
    return report


def save_report(report: DriftReport, output_path: str = None) -> Path:
    """Save DriftReport to JSON file and database.
    
    Args:
        report: DriftReport dict from generate_report()
        output_path: explicit output path, or auto-generate if None
    
    Returns:
        Path object of saved file
    """
    if output_path is None:
        output_path = get_output_report_path()
    else:
        output_path = Path(output_path)
    
    # Create parent directory if needed
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Save to JSON file
    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    # Save to database
    db.save_run(report)
    
    return output_path


def load_report(report_path: str) -> DriftReport:
    """Load a saved DriftReport from JSON file.
    
    Args:
        report_path: path to report JSON file
    
    Returns:
        DriftReport dict
    """
    with open(report_path, 'r') as f:
        report = json.load(f)
    return report


def print_report_summary(report: DriftReport) -> None:
    """Print human-readable summary to terminal.
    
    Args:
        report: DriftReport dict
    """
    summary = report.get('summary', {})
    
    print()
    print("=" * 70)
    print(f"📊 DriftGuard Analysis Report")
    print(f"Repository: {report.get('repo', 'unknown')}")
    print(f"Analysis window: last {report.get('analysis_window_days', 0)} days")
    print(f"Analyzed at: {report.get('analyzed_at', 'unknown')}")
    print("=" * 70)
    
    print()
    print("📈 Summary Statistics:")
    print(f"  Total files analyzed: {summary.get('total_files', 0)}")
    print(f"  🔴 CRITICAL:  {summary.get('critical_count', 0)} files")
    print(f"  🟠 AT_RISK:   {summary.get('at_risk_count', 0)} files")
    print(f"  🟡 WATCH:     {summary.get('watch_count', 0)} files")
    print(f"  🟢 HEALTHY:   {summary.get('healthy_count', 0)} files")
    print(f"  Average score: {summary.get('average_health_score', 0):.1f}/100")
    
    print()
    print("⚠️  Top Concerns (worst 3 files):")
    files = report.get('files', [])
    for i, f in enumerate(files[:3], 1):
        path = f.get('file_path', 'unknown')
        score = f.get('health_score', 0)
        status = f.get('status_emoji', '❓')
        risk = f.get('top_risk', 'N/A')
        print(f"  {i}. {status} {path} ({score}/100)")
        print(f"     Risk: {risk}")
    
    print()
    print("✅ Healthiest (best 3 files):")
    for i, f in enumerate(files[-3:] if len(files) > 3 else [], 1):
        path = f.get('file_path', 'unknown')
        score = f.get('health_score', 0)
        status = f.get('status_emoji', '❓')
        print(f"  {i}. {status} {path} ({score}/100)")
    
    print()
    print("=" * 70)
