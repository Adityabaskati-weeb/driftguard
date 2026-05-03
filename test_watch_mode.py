"""Test script for watch mode functionality.

Quick validation that watch mode can start and run at least one cycle.
"""
import subprocess
import time
import sys
from pathlib import Path

def test_watch_mode():
    """Test that watch mode starts and runs successfully."""
    print("Testing DriftGuard watch mode...")
    print("=" * 70)
    
    # Start watch mode with very short interval (10 seconds)
    cmd = [
        sys.executable,
        "driftguard.py",
        "--repo", ".",
        "--days", "7",
        "--max-files", "3",
        "--watch",
        "--interval", "10s"
    ]
    
    print(f"Running: {' '.join(cmd)}")
    print("Will run for 15 seconds then stop...")
    print("=" * 70)
    
    # Start the process
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    # Let it run for 15 seconds (should complete at least one cycle)
    start_time = time.time()
    output_lines = []
    
    try:
        while time.time() - start_time < 15:
            line = process.stdout.readline()
            if line:
                print(line.rstrip())
                output_lines.append(line)
            
            # Check if process ended
            if process.poll() is not None:
                break
            
            time.sleep(0.1)
    finally:
        # Terminate the process
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
    
    print("\n" + "=" * 70)
    print("Test completed!")
    
    # Check if logs directory was created
    logs_dir = Path("logs")
    if logs_dir.exists():
        print("✓ Logs directory created")
        log_file = logs_dir / "driftguard.log"
        if log_file.exists():
            print(f"✓ Log file created: {log_file}")
            print(f"  Size: {log_file.stat().st_size} bytes")
        else:
            print("✗ Log file not found")
    else:
        print("✗ Logs directory not created")
    
    # Check if database was initialized
    db_file = Path("data/driftguard.db")
    if db_file.exists():
        print(f"✓ Database file exists: {db_file}")
    else:
        print("✗ Database file not found")
    
    print("=" * 70)

if __name__ == "__main__":
    test_watch_mode()

# Made with Bob
