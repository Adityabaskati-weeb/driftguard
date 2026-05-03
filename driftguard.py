"""DriftGuard CLI entrypoint.

Run: python driftguard.py --repo . --days 30
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

# Add app directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from app.git_parser import get_file_diffs
from app.bob_analyzer import batch_analyze
from app.scorer import score_all_files, generate_summary, print_summary_table
from app.report_generator import generate_report, save_report
from app.config import Config, get_output_report_path
from app.exceptions import InvalidRepositoryError, GitOperationError

from app.git_parser import get_file_diffs
from app.bob_analyzer import batch_analyze
from app.scorer import score_all_files
from app.report_generator import generate_report, save_report, print_report_summary


def main():
    """Main CLI entrypoint."""
    import io
    
    # Set UTF-8 encoding for Windows console
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    
    parser = argparse.ArgumentParser(
        description="DriftGuard — Codebase Decay Monitor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python driftguard.py --repo . --days 30
  python driftguard.py --repo /path/to/project --days 14 --max-files 10
  python driftguard.py --repo . --days 7 --output custom_report.json --verbose

After running, start the dashboard:
  uvicorn app.main:app --reload
  Then open: http://localhost:8000
        """
    )
    
    parser.add_argument(
        "--repo",
        default=".",
        help="Path to git repository (default: current directory)"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=Config.DEFAULT_DAYS,
        help=f"Number of days of history to analyze (default: {Config.DEFAULT_DAYS})"
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSON file path (default: auto-generated in output/ directory)"
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=Config.DEFAULT_MAX_FILES,
        help=f"Max number of files to analyze (default: {Config.DEFAULT_MAX_FILES})"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed analysis for each file"
    )
    
    args = parser.parse_args()
    
    # Print banner
    print("\n" + "=" * 80)
    print("🔍 DriftGuard — Codebase Decay Monitor")
    print("=" * 80)
    from datetime import timezone
    print(f"Repository: {args.repo}")
    print(f"Analysis window: Last {args.days} days")
    print(f"Max files: {args.max_files}")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}")
    print("=" * 80)
    
    try:
        # Step 1: Parse Git repository
        print(f"\n📂 Step 1/4: Parsing Git history...")
        file_diffs = get_file_diffs(args.repo, args.days)
        
        if not file_diffs:
            print("\n⚠️  No files found in the analysis window.")
            print(f"   Try increasing --days or check if {args.repo} is a git repository.")
            print(f"   Current setting: --days {args.days}")
            return 1
        
        print(f"✅ Found {len(file_diffs)} modified files")
        
        # Limit to max_files (take most-changed files first)
        if len(file_diffs) > args.max_files:
            print(f"⚠️  Limiting analysis to top {args.max_files} most-changed files")
            file_diffs = file_diffs[:args.max_files]
        
        # Step 2: Analyze with Bob
        print(f"\n🤖 Step 2/4: Analyzing with IBM Bob...")
        analyses = batch_analyze(file_diffs, delay=2.0)
        
        if args.verbose:
            print("\n" + "=" * 80)
            print("DETAILED ANALYSIS RESULTS")
            print("=" * 80)
            for analysis in analyses:
                print(f"\n📄 {analysis['file_path']}")
                print(f"   Language: {analysis['language']}")
                print(f"   Commits: {analysis['total_commits']}")
                print(f"   Scores:")
                print(f"     - Documentation: {analysis.get('documentation_drift_score', 'N/A')}/100")
                print(f"     - Test Coverage: {analysis.get('test_drift_score', 'N/A')}/100")
                print(f"     - Complexity: {analysis.get('complexity_growth_score', 'N/A')}/100")
                print(f"     - Naming: {analysis.get('naming_consistency_score', 'N/A')}/100")
                print(f"   Summary: {analysis.get('decay_summary', 'N/A')}")
                print(f"   Top Risk: {analysis.get('top_risk', 'N/A')}")
                print(f"   Recommendation: {analysis.get('recommendation', 'N/A')}")
        
        # Step 3: Calculate health scores
        print(f"\n📊 Step 3/4: Calculating health scores...")
        scored_files = score_all_files(analyses)
        print(f"✅ Scored {len(scored_files)} files")
        
        # Step 4: Generate report
        print(f"\n📝 Step 4/4: Generating report...")
        report = generate_report(
            scored_files=scored_files,
            repo_path=args.repo,
            analysis_days=args.days,
            metadata={
                'max_files': args.max_files,
                'cli_version': '1.0.0'
            }
        )
        
        # Determine output path
        if args.output:
            output_path = args.output
        else:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            output_path = get_output_report_path(timestamp)
        
        # Save report
        save_report(report, str(output_path))
        
        # Print summary table
        print_summary_table(scored_files)
        
        # Print final instructions
        print("=" * 80)
        print("✅ Analysis complete!")
        print(f"📄 Full report saved to: {output_path}")
        print("\n🚀 Next steps:")
        print("   1. Start the dashboard:")
        print("      uvicorn app.main:app --reload")
        print("   2. Open in browser:")
        print("      http://localhost:8000")
        print("=" * 80)
        print()
        
        return 0
        
    except InvalidRepositoryError as e:
        print(f"\n❌ Error: {e}")
        print(f"   '{args.repo}' is not a valid git repository.")
        print("   Make sure you're pointing to a directory with a .git folder.")
        return 1
        
    except GitOperationError as e:
        print(f"\n❌ Git Error: {e}")
        print("   There was a problem reading the git history.")
        return 1
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Analysis interrupted by user.")
        return 130
        
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())

# Made with Bob
