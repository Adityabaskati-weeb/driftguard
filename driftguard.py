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

from app.git_parser import get_file_diffs
from app.bob_analyzer import batch_analyze
from app.scorer import score_all_files
from app.report_generator import generate_report, save_report, print_report_summary
from app.db import initialize_db, save_run
from app.alert_manager import AlertManager


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
    print("\n⚠️  Shutdown requested. Finishing current run...")
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
                 logger: logging.Logger = None) -> dict:
    """Run a single analysis cycle.
    
    Args:
        repo: Path to git repository
        days: Days of history to analyze
        max_files: Maximum files to analyze
        output: Optional output file path
        logger: Optional logger instance
        
    Returns:
        Generated report dict
    """
    if logger is None:
        logger = logging.getLogger("driftguard")
    
    logger.info(f"Starting analysis: repo={repo}, days={days}, max_files={max_files}")
    
    # Step 1: Extract git diffs
    try:
        file_diffs = get_file_diffs(repo, days)
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
            alert_config: dict = None):
    """Run continuous analysis with scheduled intervals.
    
    Args:
        repo: Path to git repository
        days: Days of history to analyze
        max_files: Maximum files to analyze
        interval_seconds: Seconds between analysis runs
        alert_config: Optional alert configuration dict
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
            report = run_analysis(repo, days, max_files, logger=logger)
            
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


def main():
    parser = argparse.ArgumentParser(description="DriftGuard - Codebase Decay Monitor")
    parser.add_argument("--repo", default=".", help="Path to git repository (default: .)")
    parser.add_argument("--days", type=int, default=30, help="Days of history to analyze (default: 30)")
    parser.add_argument("--output", default=None, help="Output JSON file path (auto-generated if not provided)")
    parser.add_argument("--max-files", type=int, default=20, help="Max files to analyze (default: 20)")
    parser.add_argument("--verbose", action="store_true", help="Print raw analysis details")
    parser.add_argument("--watch", action="store_true", help="Run in watch mode with scheduled intervals")
    parser.add_argument("--interval", default="24h", help="Watch mode interval (e.g., '24h', '30m', '3600')")
    
    args = parser.parse_args()
    
    # Watch mode
    if args.watch:
        try:
            interval_seconds = parse_interval(args.interval)
        except ValueError as e:
            print(f"❌ {e}")
            sys.exit(1)
        
        # Run watcher
        watcher(args.repo, args.days, args.max_files, interval_seconds)
        sys.exit(0)
    
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
        analyses = batch_analyze(file_diffs)
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
