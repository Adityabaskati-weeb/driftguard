"""DriftGuard CLI entrypoint.

Full pipeline: git_parser → bob_analyzer → scorer → report_generator → dashboard

Run: python driftguard.py --repo . --days 30
Watch mode: python driftguard.py --watch --interval 24h
"""
import argparse
import sys
import signal
import time
import re
import logging
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler

from app.git_parser import get_file_diffs, resolve_repo, _fetch_github_repo_diffs
from app.bob_analyzer import batch_analyze
from app.scorer import score_all_files
from app.report_generator import generate_report, save_report, print_report_summary
from app.report_exporter import export_report
from app.db import initialize_db, save_run
from app.alert_manager import AlertManager
from app.remediation import generate_remediations_for_files
from app.config import get_language_config_info
from app.validation import (
    ValidationError,
    validate_repo_path,
    validate_days,
    validate_max_files,
    validate_interval,
    validate_export_mode
)


# Global flag for graceful shutdown
shutdown_requested = False


def setup_logging(log_file: str = "logs/driftguard.log") -> logging.Logger:
    """Set up logging with rotating file handler and console output.
    
    Args:
        log_file: Path to log file (default: logs/driftguard.log)
        
    Returns:
        Configured logger instance
    """
    # Create logs directory if it doesn't exist
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Create logger
    logger = logging.getLogger("driftguard")
    logger.setLevel(logging.INFO)
    
    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # File handler with rotation (10MB max, keep 5 backups)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)
    
    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


def signal_handler(signum, frame):
    """Handle SIGINT (Ctrl+C) for graceful shutdown."""
    global shutdown_requested
    print("\n[!] Shutdown requested. Finishing current run...")
    shutdown_requested = True


def parse_interval(interval_str: str) -> int:
    """Parse interval string to seconds.
    
    Supports formats:
    - "24h" -> 86400 seconds
    - "30m" -> 1800 seconds
    - "3600" -> 3600 seconds (plain number)
    
    Args:
        interval_str: Interval string (e.g., "24h", "30m", "3600")
        
    Returns:
        Interval in seconds
        
    Raises:
        ValueError: If interval format is invalid
    """
    # Try plain number first
    try:
        return int(interval_str)
    except ValueError:
        pass
    
    # Parse with unit suffix
    match = re.match(r'^(\d+)([hms])$', interval_str.lower())
    if not match:
        raise ValueError(
            f"Invalid interval format: {interval_str}. "
            "Use format like '24h', '30m', '3600s', or plain seconds."
        )
    
    value, unit = match.groups()
    value = int(value)
    
    if unit == 'h':
        return value * 3600
    elif unit == 'm':
        return value * 60
    elif unit == 's':
        return value
    
    raise ValueError(f"Invalid time unit: {unit}")


def run_analysis(repo: str, days: int, max_files: int, output: str = None,
                 logger: logging.Logger = None, github_token: str = None) -> dict:
    """Run a single analysis cycle.
    
    Args:
        repo: Path to git repository or GitHub URL
        days: Days of history to analyze
        max_files: Maximum files to analyze
        output: Optional output file path
        logger: Optional logger instance
        github_token: Optional GitHub token for API access
        
    Returns:
        Generated report dict
    """
    if logger is None:
        logger = logging.getLogger("driftguard")
    
    logger.info(f"Starting analysis: repo={repo}, days={days}, max_files={max_files}")
    
    # Step 1: Resolve repository (local, GitHub, or other remote)
    try:
        repo_data, is_remote = resolve_repo(repo, github_token)
        
        # If it's a GitHub repo, fetch diffs via API
        if is_remote:
            owner, repo_name, token = repo_data
            logger.info(f"Fetching data from GitHub API: {owner}/{repo_name}")
            file_diffs = _fetch_github_repo_diffs(owner, repo_name, days, token)
        else:
            # Local repo or cloned repo
            file_diffs = get_file_diffs(repo_data, days)
    except Exception as e:
        logger.error(f"Error reading repository: {e}")
        raise
    
    if not file_diffs:
        logger.warning("No modified files found in the analysis window")
        return None
    
    logger.info(f"Found {len(file_diffs)} modified files")
    
    # Limit to max_files
    if len(file_diffs) > max_files:
        logger.info(f"Limiting to top {max_files} most-changed files")
        file_diffs = file_diffs[:max_files]
    
    # Step 2: Analyze with bob_analyzer
    logger.info(f"Analyzing {len(file_diffs)} files for decay signals")
    try:
        analyses = batch_analyze(file_diffs)
    except Exception as e:
        logger.error(f"Error during analysis: {e}")
        raise
    
    # Step 3: Score files
    logger.info("Calculating health scores")
    try:
        scored_files = score_all_files(analyses)
    except Exception as e:
        logger.error(f"Error during scoring: {e}")
        raise
    
    # Step 4: Generate report
    logger.info("Generating report")
    try:
        report = generate_report(repo, days, scored_files)
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        raise
    
    # Step 5: Save report
    try:
        report_path = save_report(report, output)
        logger.info(f"Report saved to {report_path}")
    except Exception as e:
        logger.error(f"Error saving report: {e}")
        raise
    
    return report


def watcher(repo: str, days: int, max_files: int, interval_seconds: int,
            alert_config: dict = None, github_token: str = None):
    """Run continuous analysis with scheduled intervals.
    
    Args:
        repo: Path to git repository or GitHub URL
        days: Days of history to analyze
        max_files: Maximum files to analyze
        interval_seconds: Seconds between analysis runs
        alert_config: Optional alert configuration dict
        github_token: Optional GitHub token for API access
    """
    global shutdown_requested
    
    # Set up logging
    logger = setup_logging()
    logger.info("=" * 70)
    logger.info("DriftGuard Watch Mode Started")
    logger.info("=" * 70)
    logger.info(f"Repository: {repo}")
    logger.info(f"Analysis window: {days} days")
    logger.info(f"Max files: {max_files}")
    logger.info(f"Interval: {interval_seconds} seconds ({interval_seconds/3600:.1f} hours)")
    logger.info("=" * 70)
    
    # Initialize database
    initialize_db()
    logger.info("Database initialized")
    
    # Initialize alert manager
    alert_manager = AlertManager(alert_config)
    
    # Register signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    run_count = 0
    
    while not shutdown_requested:
        run_count += 1
        logger.info(f"\n{'=' * 70}")
        logger.info(f"Starting analysis run #{run_count}")
        logger.info(f"{'=' * 70}")
        
        try:
            # Run analysis
            report = run_analysis(repo, days, max_files, logger=logger, github_token=github_token)
            
            if report:
                # Save to database
                run_id = save_run(report)
                logger.info(f"Run saved to database: {run_id}")
                
                # Check for alerts
                alert_manager.check_and_alert(report)
                
                # Print summary
                print_report_summary(report)
            else:
                logger.info("No changes detected, skipping database save")
            
            logger.info(f"Analysis run #{run_count} completed successfully")
            
        except Exception as e:
            logger.error(f"Error during analysis run #{run_count}: {e}", exc_info=True)
        
        if shutdown_requested:
            break
        
        # Wait for next interval
        logger.info(f"Next run in {interval_seconds} seconds ({interval_seconds/3600:.1f} hours)")
        logger.info(f"Press Ctrl+C to stop gracefully")
        
        # Sleep in small increments to allow for responsive shutdown
        sleep_interval = 1  # Check every second
        for _ in range(interval_seconds):
            if shutdown_requested:
                break
            time.sleep(sleep_interval)
    
    logger.info("\n" + "=" * 70)
    logger.info("DriftGuard Watch Mode Stopped")
    logger.info(f"Total runs completed: {run_count}")
    logger.info("=" * 70)


def print_language_config():
    """Print active language configuration to console."""
    print("\n" + "=" * 70)
    print("DriftGuard Language Configuration")
    print("=" * 70)
    
    try:
        config_info = get_language_config_info()
        
        print(f"\nConfiguration File: {config_info['config_path']}")
        print(f"Version: {config_info['version']}")
        print(f"Description: {config_info['description']}")
        
        print(f"\n[ENABLED] Extensions ({config_info['total_enabled']}):")
        print("-" * 70)
        for ext_info in config_info['enabled_extensions']:
            ext = ext_info['extension']
            lang = ext_info['language']
            desc = ext_info['description']
            print(f"  {ext:8} -> {lang:15} ({desc})")
        
        if config_info['disabled_extensions']:
            print(f"\n[DISABLED] Extensions ({config_info['total_disabled']}):")
            print("-" * 70)
            for ext_info in config_info['disabled_extensions']:
                ext = ext_info['extension']
                lang = ext_info['language']
                desc = ext_info['description']
                print(f"  {ext:8} -> {lang:15} ({desc})")
        
        print("\n" + "=" * 70)
        print(f"Total: {config_info['total_enabled']} enabled, {config_info['total_disabled']} disabled")
        print("=" * 70)
        
    except Exception as e:
        print(f"[ERROR] Error loading language configuration: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="DriftGuard - Codebase Decay Monitor")
    parser.add_argument("--repo", default=".", help="Path to git repository or GitHub URL (default: .)")
    parser.add_argument("--days", type=int, default=30, help="Days of history to analyze (default: 30)")
    parser.add_argument("--output", default=None, help="Output JSON file path (auto-generated if not provided)")
    parser.add_argument("--max-files", type=int, default=20, help="Max files to analyze (default: 20)")
    parser.add_argument("--verbose", action="store_true", help="Print raw analysis details")
    parser.add_argument("--watch", action="store_true", help="Run in watch mode with scheduled intervals")
    parser.add_argument("--interval", default="24h", help="Watch mode interval (e.g., '24h', '30m', '3600')")
    parser.add_argument("--github-token", default=None, help="GitHub token for API access (overrides GITHUB_TOKEN env var)")
    parser.add_argument("--export", default="json", choices=["json", "markdown", "pdf", "all"],
                        help="Export format: json, markdown, pdf, or all (default: json)")
    parser.add_argument("--remediate", action="store_true",
                        help="Generate remediation files for CRITICAL and AT_RISK files")
    parser.add_argument("--show-languages", action="store_true",
                        help="Show active language configuration and exit")
    
    args = parser.parse_args()
    
    # Handle --show-languages flag
    if args.show_languages:
        print_language_config()
        sys.exit(0)
    
    # Validate inputs
    try:
        validate_days(args.days)
        validate_max_files(args.max_files)
        validate_export_mode(args.export)
        validate_repo_path(args.repo, args.github_token)
    except ValidationError as e:
        print(f"ERROR: {e.message}", file=sys.stderr)
        if e.hint:
            print(f"HINT: {e.hint}", file=sys.stderr)
        sys.exit(1)
    
    # Watch mode
    if args.watch:
        try:
            validate_interval(args.interval)
            interval_seconds = parse_interval(args.interval)
        except ValidationError as e:
            print(f"ERROR: {e.message}", file=sys.stderr)
            if e.hint:
                print(f"HINT: {e.hint}", file=sys.stderr)
            sys.exit(1)
        except ValueError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)
        
        # Run watcher
        watcher(args.repo, args.days, args.max_files, interval_seconds, github_token=args.github_token)
        sys.exit(0)
    
    print("\n" + "=" * 70)
    print("DriftGuard - Codebase Decay Monitor")
    print("=" * 70)
    
    # Step 1: Resolve repository and extract git diffs
    print(f"\n[*] Scanning {args.repo} for last {args.days} days of changes...")
    try:
        repo_data, is_remote = resolve_repo(args.repo, args.github_token)
        
        # If it's a GitHub repo, fetch diffs via API
        if is_remote:
            owner, repo_name, token = repo_data
            print(f"Using GitHub API for {owner}/{repo_name}")
            file_diffs = _fetch_github_repo_diffs(owner, repo_name, args.days, token)
        else:
            # Local repo or cloned repo
            file_diffs = get_file_diffs(repo_data, args.days)
    except Exception as e:
        print(f"[ERROR] Error reading repository: {e}")
        sys.exit(1)
    
    if not file_diffs:
        print("[!] No modified files found in the analysis window.")
        sys.exit(0)
    
    print(f"[+] Found {len(file_diffs)} modified files")
    
    # Limit to max_files
    if len(file_diffs) > args.max_files:
        print(f"[!] Limiting to top {args.max_files} most-changed files (by commit count)")
        file_diffs = file_diffs[:args.max_files]
    
    # Step 2: Analyze with bob_analyzer
    print(f"\n[*] Analyzing {len(file_diffs)} files for decay signals...")
    try:
        analyses = batch_analyze(file_diffs)
    except Exception as e:
        print(f"[ERROR] Error during analysis: {e}")
        sys.exit(1)
    
    print(f"[+] Analysis complete")
    
    # Step 3: Score files
    print("\n[*] Calculating health scores...")
    try:
        scored_files = score_all_files(analyses)
    except Exception as e:
        print(f"[ERROR] Error during scoring: {e}")
        sys.exit(1)
    
    print(f"[+] Scoring complete")
    
    # Step 4: Generate report
    print("\n[*] Generating report...")
    try:
        report = generate_report(args.repo, args.days, scored_files)
    except Exception as e:
        print(f"[ERROR] Error generating report: {e}")
        sys.exit(1)
    
    # Step 5: Save report (JSON by default)
    try:
        report_path = save_report(report, args.output)
    except Exception as e:
        print(f"[ERROR] Error saving report: {e}")
        sys.exit(1)
    
    print(f"[+] Report saved to {report_path}")
    
    # Step 6: Export to additional formats if requested
    if args.export != "json":
        print(f"\n[*] Exporting report in {args.export} format...")
        try:
            export_result = export_report(report, args.export, output_dir="output")
            print(f"[+] {export_result}")
        except ImportError as e:
            print(f"[!] Export failed: {e}")
            print("   Install weasyprint for PDF export: pip install weasyprint")
        except Exception as e:
            print(f"[ERROR] Error exporting report: {e}")
    
    # Step 7: Generate remediation files if requested
    if args.remediate:
        print("\n[*] Generating remediation files...")
        try:
            # Initialize database connection
            initialize_db()
            import sqlite3
            db_conn = sqlite3.connect("data/driftguard.db")
            
            try:
                remediation_count = generate_remediations_for_files(
                    scored_files,
                    args.repo,
                    db_conn
                )
                print(f"[+] Generated {remediation_count} remediation files in remediation/")
            finally:
                db_conn.close()
        except Exception as e:
            print(f"[ERROR] Error generating remediation files: {e}")
    
    # Print summary
    print_report_summary(report)
    
    print("\n[*] Start dashboard: uvicorn app.main:app --reload")
    print("=" * 70 + "\n")


if __name__ == '__main__':
    main()
