"""test_rate_limiter.py

Comprehensive tests for the TokenBucketRateLimiter.
Tests burst behavior, refill behavior, thread safety, and edge cases.
"""
import time
import threading
import pytest
from app.rate_limiter import TokenBucketRateLimiter


class TestTokenBucketRateLimiter:
    """Test suite for TokenBucketRateLimiter."""
    
    def test_initialization(self):
        """Test rate limiter initialization with valid parameters."""
        limiter = TokenBucketRateLimiter(tokens_per_minute=60, burst_capacity=10)
        assert limiter.tokens_per_minute == 60
        assert limiter.burst_capacity == 10
        assert limiter.refill_rate == 1.0  # 60 tokens/min = 1 token/sec
        assert limiter.get_available_tokens() == 10.0  # Starts with full burst
    
    def test_initialization_invalid_params(self):
        """Test that invalid parameters raise ValueError."""
        with pytest.raises(ValueError, match="tokens_per_minute must be positive"):
            TokenBucketRateLimiter(tokens_per_minute=0, burst_capacity=5)
        
        with pytest.raises(ValueError, match="tokens_per_minute must be positive"):
            TokenBucketRateLimiter(tokens_per_minute=-10, burst_capacity=5)
        
        with pytest.raises(ValueError, match="burst_capacity must be positive"):
            TokenBucketRateLimiter(tokens_per_minute=30, burst_capacity=0)
        
        with pytest.raises(ValueError, match="burst_capacity must be positive"):
            TokenBucketRateLimiter(tokens_per_minute=30, burst_capacity=-5)
    
    def test_burst_behavior(self):
        """Test that burst capacity allows rapid initial requests."""
        # 60 tokens/min = 1 token/sec, burst = 5
        limiter = TokenBucketRateLimiter(tokens_per_minute=60, burst_capacity=5)
        
        # Should be able to acquire 5 tokens immediately (burst capacity)
        start_time = time.time()
        for i in range(5):
            success = limiter.try_acquire(tokens=1)
            assert success, f"Failed to acquire token {i+1} during burst"
        elapsed = time.time() - start_time
        
        # All 5 should be acquired in less than 0.5 seconds (burst behavior)
        assert elapsed < 0.5, f"Burst took too long: {elapsed}s"
        
        # 6th token should fail (burst exhausted)
        success = limiter.try_acquire(tokens=1)
        assert not success, "Should not acquire token after burst exhausted"
    
    def test_refill_behavior(self):
        """Test that tokens refill at the correct rate."""
        # 60 tokens/min = 1 token/sec
        limiter = TokenBucketRateLimiter(tokens_per_minute=60, burst_capacity=5)
        
        # Exhaust burst capacity
        for _ in range(5):
            limiter.try_acquire(tokens=1)
        
        # Wait for 2 seconds (should refill ~2 tokens)
        time.sleep(2.1)
        
        # Should be able to acquire 2 tokens
        assert limiter.try_acquire(tokens=1), "Should acquire 1st refilled token"
        assert limiter.try_acquire(tokens=1), "Should acquire 2nd refilled token"
        
        # 3rd should fail (only 2 tokens refilled)
        assert not limiter.try_acquire(tokens=1), "Should not acquire 3rd token"
    
    def test_refill_does_not_exceed_burst(self):
        """Test that refill does not exceed burst capacity."""
        # 60 tokens/min = 1 token/sec, burst = 3
        limiter = TokenBucketRateLimiter(tokens_per_minute=60, burst_capacity=3)
        
        # Wait for 10 seconds (would refill 10 tokens, but capped at burst=3)
        time.sleep(10)
        
        # Should only have 3 tokens available (burst capacity)
        assert limiter.try_acquire(tokens=1), "Should acquire 1st token"
        assert limiter.try_acquire(tokens=1), "Should acquire 2nd token"
        assert limiter.try_acquire(tokens=1), "Should acquire 3rd token"
        assert not limiter.try_acquire(tokens=1), "Should not acquire 4th token (capped at burst)"
    
    def test_acquire_blocking(self):
        """Test that acquire() blocks until tokens are available."""
        # 60 tokens/min = 1 token/sec, burst = 2
        limiter = TokenBucketRateLimiter(tokens_per_minute=60, burst_capacity=2)
        
        # Exhaust burst
        limiter.try_acquire(tokens=2)
        
        # Acquire should block for ~1 second until token refills
        start_time = time.time()
        success = limiter.acquire(tokens=1, timeout=2.0)
        elapsed = time.time() - start_time
        
        assert success, "Should successfully acquire token after waiting"
        assert 0.8 < elapsed < 1.5, f"Should wait ~1 second, waited {elapsed}s"
    
    def test_acquire_timeout(self):
        """Test that acquire() respects timeout."""
        # Very slow refill: 6 tokens/min = 0.1 token/sec
        limiter = TokenBucketRateLimiter(tokens_per_minute=6, burst_capacity=1)
        
        # Exhaust burst
        limiter.try_acquire(tokens=1)
        
        # Try to acquire with short timeout (should fail)
        start_time = time.time()
        success = limiter.acquire(tokens=1, timeout=0.5)
        elapsed = time.time() - start_time
        
        assert not success, "Should timeout before acquiring token"
        assert 0.4 < elapsed < 0.7, f"Should timeout after ~0.5s, took {elapsed}s"
    
    def test_acquire_multiple_tokens(self):
        """Test acquiring multiple tokens at once."""
        limiter = TokenBucketRateLimiter(tokens_per_minute=60, burst_capacity=10)
        
        # Acquire 5 tokens at once
        success = limiter.try_acquire(tokens=5)
        assert success, "Should acquire 5 tokens"
        assert limiter.get_available_tokens() == 5.0, "Should have 5 tokens left"
        
        # Try to acquire 6 more (should fail, only 5 available)
        success = limiter.try_acquire(tokens=6)
        assert not success, "Should not acquire 6 tokens (only 5 available)"
    
    def test_acquire_invalid_tokens(self):
        """Test that invalid token counts raise ValueError."""
        limiter = TokenBucketRateLimiter(tokens_per_minute=60, burst_capacity=5)
        
        with pytest.raises(ValueError, match="tokens must be positive"):
            limiter.acquire(tokens=0)
        
        with pytest.raises(ValueError, match="tokens must be positive"):
            limiter.try_acquire(tokens=-1)
    
    def test_get_wait_time(self):
        """Test wait time calculation."""
        # 60 tokens/min = 1 token/sec
        limiter = TokenBucketRateLimiter(tokens_per_minute=60, burst_capacity=5)
        
        # Exhaust burst
        limiter.try_acquire(tokens=5)
        
        # Wait time for 1 token should be ~1 second
        wait_time = limiter.get_wait_time(tokens=1)
        assert 0.9 < wait_time < 1.1, f"Wait time should be ~1s, got {wait_time}s"
        
        # Wait time for 3 tokens should be ~3 seconds
        wait_time = limiter.get_wait_time(tokens=3)
        assert 2.9 < wait_time < 3.1, f"Wait time should be ~3s, got {wait_time}s"
    
    def test_get_wait_time_with_available_tokens(self):
        """Test that wait time is 0 when tokens are available."""
        limiter = TokenBucketRateLimiter(tokens_per_minute=60, burst_capacity=5)
        
        # Should have 5 tokens available
        wait_time = limiter.get_wait_time(tokens=3)
        assert wait_time == 0.0, "Wait time should be 0 when tokens are available"
    
    def test_reset(self):
        """Test that reset restores full burst capacity."""
        limiter = TokenBucketRateLimiter(tokens_per_minute=60, burst_capacity=5)
        
        # Exhaust burst
        limiter.try_acquire(tokens=5)
        assert limiter.get_available_tokens() == 0.0, "Should have 0 tokens"
        
        # Reset
        limiter.reset()
        assert limiter.get_available_tokens() == 5.0, "Should have full burst after reset"
    
    def test_thread_safety(self):
        """Test that rate limiter is thread-safe."""
        limiter = TokenBucketRateLimiter(tokens_per_minute=600, burst_capacity=50)
        
        acquired_counts = []
        lock = threading.Lock()
        
        def worker():
            """Worker thread that tries to acquire tokens."""
            count = 0
            for _ in range(10):
                if limiter.try_acquire(tokens=1):
                    count += 1
                time.sleep(0.01)  # Small delay
            
            with lock:
                acquired_counts.append(count)
        
        # Start 10 threads
        threads = []
        for _ in range(10):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()
        
        # Wait for all threads
        for t in threads:
            t.join()
        
        # Total acquired should not exceed burst capacity + refills
        total_acquired = sum(acquired_counts)
        # With 10 threads * 10 attempts * 0.01s delay = ~1 second total
        # Burst = 50, refill = 600/60 = 10 tokens/sec
        # Max possible = 50 + 10 = 60 tokens
        assert total_acquired <= 60, f"Acquired too many tokens: {total_acquired}"
        assert total_acquired >= 50, f"Should acquire at least burst capacity: {total_acquired}"
    
    def test_concurrent_acquire_blocking(self):
        """Test that multiple threads can block and acquire tokens."""
        limiter = TokenBucketRateLimiter(tokens_per_minute=60, burst_capacity=2)
        
        results = []
        lock = threading.Lock()
        
        def worker(worker_id):
            """Worker that blocks to acquire a token."""
            start = time.time()
            success = limiter.acquire(tokens=1, timeout=5.0)
            elapsed = time.time() - start
            
            with lock:
                results.append({
                    'worker_id': worker_id,
                    'success': success,
                    'elapsed': elapsed
                })
        
        # Start 5 threads (burst=2, so 3 will need to wait)
        threads = []
        for i in range(5):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()
        
        # Wait for all threads
        for t in threads:
            t.join()
        
        # All should succeed
        assert all(r['success'] for r in results), "All workers should acquire tokens"
        assert len(results) == 5, "All 5 workers should complete"
        
        # First 2 should be fast (burst), next 3 should wait
        fast_workers = [r for r in results if r['elapsed'] < 0.5]
        slow_workers = [r for r in results if r['elapsed'] >= 0.5]
        
        assert len(fast_workers) == 2, f"2 workers should be fast (burst), got {len(fast_workers)}"
        assert len(slow_workers) == 3, f"3 workers should wait, got {len(slow_workers)}"
    
    def test_high_rate_limit(self):
        """Test with high rate limit (many tokens per minute)."""
        # 600 tokens/min = 10 tokens/sec
        limiter = TokenBucketRateLimiter(tokens_per_minute=600, burst_capacity=20)
        
        # Should be able to acquire 20 tokens immediately
        for i in range(20):
            success = limiter.try_acquire(tokens=1)
            assert success, f"Should acquire token {i+1}"
        
        # Wait 0.5 seconds (should refill ~5 tokens)
        time.sleep(0.5)
        
        # Should be able to acquire ~5 more tokens
        acquired = 0
        for _ in range(10):
            if limiter.try_acquire(tokens=1):
                acquired += 1
        
        assert 4 <= acquired <= 6, f"Should acquire ~5 tokens, got {acquired}"
    
    def test_low_rate_limit(self):
        """Test with low rate limit (few tokens per minute)."""
        # 6 tokens/min = 0.1 tokens/sec = 1 token per 10 seconds
        limiter = TokenBucketRateLimiter(tokens_per_minute=6, burst_capacity=2)
        
        # Exhaust burst
        limiter.try_acquire(tokens=2)
        
        # Wait time for next token should be ~10 seconds
        wait_time = limiter.get_wait_time(tokens=1)
        assert 9.5 < wait_time < 10.5, f"Wait time should be ~10s, got {wait_time}s"


def test_rate_limiter_integration():
    """Integration test simulating real usage pattern."""
    # Simulate 30 calls per minute with burst of 5
    limiter = TokenBucketRateLimiter(tokens_per_minute=30, burst_capacity=5)
    
    call_times = []
    
    # Make 10 calls
    for i in range(10):
        wait_time = limiter.get_wait_time(tokens=1)
        if wait_time > 0:
            print(f"Call {i+1}: Waiting {wait_time:.2f}s")
        
        start = time.time()
        limiter.acquire(tokens=1)
        call_times.append(time.time() - start)
    
    # First 5 calls should be fast (burst)
    assert all(t < 0.1 for t in call_times[:5]), "First 5 calls should be fast (burst)"
    
    # Remaining calls should have some delay
    assert any(t > 0.5 for t in call_times[5:]), "Later calls should have delays"
    
    print(f"\nCall times: {[f'{t:.2f}s' for t in call_times]}")


if __name__ == '__main__':
    # Run tests with pytest
    pytest.main([__file__, '-v', '-s'])

# Made with Bob
