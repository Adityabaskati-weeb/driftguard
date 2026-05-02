"""DriftGuard CLI entrypoint.

Full pipeline: git_parser → bob_analyzer → scorer → report_generator → dashboard

Run: python driftguard.py --repo . --days 30
"""
import argparse
import sys
from pathlib import Path
from datetime import datetime

from app.git_parser import get_file_diffs
from app.bob_analyzer import batch_analyze
from app.scorer import score_all_files
from app.report_generator import generate_report, save_report, print_report_summary


def main():
    parser = argparse.ArgumentParser(description="🔍 DriftGuard — Codebase Decay Monitor")
    parser.add_argument("--repo", default=".", help="Path to git repository (default: .)")
    parser.add_argument("--days", type=int, default=30, help="Days of history to analyze (default: 30)")
    parser.add_argument("--output", default=None, help="Output JSON file path (auto-generated if not provided)")
    parser.add_argument("--max-files", type=int, default=20, help="Max files to analyze (default: 20)")
    parser.add_argument("--verbose", action="store_true", help="Print raw analysis details")
    
    args = parser.parse_args()
    
    print("\n" + "=" * 70)
    print("🔍 DriftGuard — Codebase Decay Monitor")
    print("=" * 70)
    
    # Step 1: Extract git diffs
    print(f"\n📂 Scanning {args.repo} for last {args.days} days of changes...")
    try:
        file_diffs = get_file_diffs(args.repo, args.days)
    except Exception as e:
        print(f"❌ Error reading repository: {e}")
        sys.exit(1)
    
    if not file_diffs:
        print("⚠️  No modified files found in the analysis window.")
        sys.exit(0)
    
    print(f"✅ Found {len(file_diffs)} modified files")
    
    # Limit to max_files
    if len(file_diffs) > args.max_files:
        print(f"⚠️  Limiting to top {args.max_files} most-changed files (by commit count)")
        file_diffs = file_diffs[:args.max_files]
    
    # Step 2: Analyze with bob_analyzer
    print(f"\n🤖 Analyzing {len(file_diffs)} files for decay signals...")
    try:
        analyses = batch_analyze(file_diffs, verbose=args.verbose)
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        sys.exit(1)
    
    print(f"✅ Analysis complete")
    
    # Step 3: Score files
    print("\n⚖️  Calculating health scores...")
    try:
        scored_files = score_all_files(analyses)
    except Exception as e:
        print(f"❌ Error during scoring: {e}")
        sys.exit(1)
    
    print(f"✅ Scoring complete")
    
    # Step 4: Generate report
    print("\n📊 Generating report...")
    try:
        report = generate_report(args.repo, args.days, scored_files)
    except Exception as e:
        print(f"❌ Error generating report: {e}")
        sys.exit(1)
    
    # Step 5: Save report
    try:
        report_path = save_report(report, args.output)
    except Exception as e:
        print(f"❌ Error saving report: {e}")
        sys.exit(1)
    
    print(f"✅ Report saved to {report_path}")
    
    # Print summary
    print_report_summary(report)
    
    print("\n🚀 Start dashboard: uvicorn app.main:app --reload")
    print("=" * 70 + "\n")


if __name__ == '__main__':
    main()
