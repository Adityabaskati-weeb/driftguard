"""demo_rate_limiter.py

Demonstration of the rate limiter functionality.
Shows burst behavior, refill behavior, and rate limiting in action.
"""
import time
from app.rate_limiter import TokenBucketRateLimiter


def demo_burst_behavior():
    """Demonstrate burst capacity allowing rapid initial requests."""
    print("\n" + "=" * 70)
    print("DEMO 1: Burst Behavior")
    print("=" * 70)
    print("Rate limit: 30 calls/min (1 call every 2 seconds)")
    print("Burst capacity: 5 calls")
    print()
    
    limiter = TokenBucketRateLimiter(tokens_per_minute=30, burst_capacity=5)
    
    print("Making 8 requests...")
    for i in range(8):
        wait_time = limiter.get_wait_time(tokens=1)
        if wait_time > 0:
            print(f"Request {i+1}: Rate limiter waiting {wait_time:.1f}s before next Bob request")
        else:
            print(f"Request {i+1}: Immediate (using burst capacity)")
        
        start = time.time()
        limiter.acquire(tokens=1)
        elapsed = time.time() - start
        
        if elapsed > 0.1:
            print(f"           > Waited {elapsed:.1f}s")
    
    print("\nOK First 5 requests used burst capacity (immediate)")
    print("OK Requests 6-8 had to wait for token refill")


def demo_refill_behavior():
    """Demonstrate token refill over time."""
    print("\n" + "=" * 70)
    print("DEMO 2: Token Refill Behavior")
    print("=" * 70)
    print("Rate limit: 60 calls/min (1 call per second)")
    print("Burst capacity: 3 calls")
    print()
    
    limiter = TokenBucketRateLimiter(tokens_per_minute=60, burst_capacity=3)
    
    # Exhaust burst
    print("Exhausting burst capacity (3 tokens)...")
    for i in range(3):
        limiter.try_acquire(tokens=1)
        print(f"  Token {i+1} acquired")
    
    print(f"\nAvailable tokens: {limiter.get_available_tokens():.1f}")
    print("\nWaiting 2 seconds for refill...")
    time.sleep(2)
    
    print(f"Available tokens after 2s: {limiter.get_available_tokens():.1f}")
    print("OK Tokens refilled at rate of 1 token/second")


def demo_rate_limiting_in_action():
    """Demonstrate rate limiting with realistic scenario."""
    print("\n" + "=" * 70)
    print("DEMO 3: Rate Limiting in Action (Realistic Scenario)")
    print("=" * 70)
    print("Simulating batch analysis of 10 files")
    print("Rate limit: 30 calls/min, Burst: 5")
    print()
    
    limiter = TokenBucketRateLimiter(tokens_per_minute=30, burst_capacity=5)
    
    files = [f"file_{i}.py" for i in range(1, 11)]
    
    start_time = time.time()
    for i, file_path in enumerate(files, 1):
        wait_time = limiter.get_wait_time(tokens=1)
        
        if wait_time > 0:
            print(f"[{i}/10] Analyzing: {file_path}")
            print(f"        [RATE LIMIT] Waiting {wait_time:.1f}s before next Bob request")
        else:
            print(f"[{i}/10] Analyzing: {file_path}")
        
        limiter.acquire(tokens=1)
        
        # Simulate analysis work
        time.sleep(0.1)
    
    total_time = time.time() - start_time
    print(f"\nOK Completed 10 analyses in {total_time:.1f}s")
    print(f"OK First 5 used burst (fast), remaining 5 were rate limited")


def demo_configuration_options():
    """Show different configuration options."""
    print("\n" + "=" * 70)
    print("DEMO 4: Configuration Options")
    print("=" * 70)
    
    configs = [
        (30, 5, "Default: 30 calls/min, burst 5"),
        (60, 10, "High throughput: 60 calls/min, burst 10"),
        (10, 2, "Conservative: 10 calls/min, burst 2"),
    ]
    
    for rate, burst, description in configs:
        print(f"\n{description}")
        limiter = TokenBucketRateLimiter(tokens_per_minute=rate, burst_capacity=burst)
        
        # Show burst
        print(f"  Burst capacity: {burst} immediate calls")
        
        # Show refill rate
        refill_rate = rate / 60.0
        print(f"  Refill rate: {refill_rate:.2f} tokens/second")
        
        # Show wait time after burst
        for _ in range(burst):
            limiter.try_acquire(tokens=1)
        wait_time = limiter.get_wait_time(tokens=1)
        print(f"  Wait time after burst: {wait_time:.1f}s")


def main():
    """Run all demonstrations."""
    print("\n" + "=" * 70)
    print("DriftGuard Rate Limiter Demonstration")
    print("=" * 70)
    
    demo_burst_behavior()
    demo_refill_behavior()
    demo_rate_limiting_in_action()
    demo_configuration_options()
    
    print("\n" + "=" * 70)
    print("All demonstrations complete!")
    print("=" * 70)
    print("\nConfiguration via environment variables:")
    print("  BOB_RATE_LIMIT_PER_MINUTE=30  # Max calls per minute")
    print("  BOB_RATE_LIMIT_BURST=5        # Burst capacity")
    print()


if __name__ == '__main__':
    main()

# Made with Bob
