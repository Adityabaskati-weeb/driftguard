"""rate_limiter.py

Token-bucket rate limiter for controlling Bob analysis call frequency.
Thread-safe implementation with configurable tokens per minute and burst capacity.
"""
import time
import threading
from typing import Optional


class TokenBucketRateLimiter:
    """Thread-safe token bucket rate limiter.
    
    Implements the token bucket algorithm to control the rate of operations.
    Tokens are added at a constant rate (tokens_per_minute) and operations
    consume tokens. If no tokens are available, the operation waits.
    
    Attributes:
        tokens_per_minute: Rate at which tokens are added (operations per minute)
        burst_capacity: Maximum tokens that can accumulate (burst size)
    """
    
    def __init__(self, tokens_per_minute: int = 30, burst_capacity: int = 5):
        """Initialize the rate limiter.
        
        Args:
            tokens_per_minute: Number of tokens added per minute (default: 30)
            burst_capacity: Maximum tokens that can be stored (default: 5)
        """
        if tokens_per_minute <= 0:
            raise ValueError("tokens_per_minute must be positive")
        if burst_capacity <= 0:
            raise ValueError("burst_capacity must be positive")
        
        self.tokens_per_minute = tokens_per_minute
        self.burst_capacity = burst_capacity
        
        # Calculate token refill rate in tokens per second
        self.refill_rate = tokens_per_minute / 60.0
        
        # Current number of tokens (start with full burst capacity)
        self._tokens = float(burst_capacity)
        
        # Last time tokens were added
        self._last_refill = time.time()
        
        # Lock for thread safety
        self._lock = threading.Lock()
    
    def _refill_tokens(self) -> None:
        """Refill tokens based on elapsed time since last refill.
        
        This method should be called while holding the lock.
        """
        now = time.time()
        elapsed = now - self._last_refill
        
        # Calculate tokens to add based on elapsed time
        tokens_to_add = elapsed * self.refill_rate
        
        # Add tokens but don't exceed burst capacity
        self._tokens = min(self.burst_capacity, self._tokens + tokens_to_add)
        
        # Update last refill time
        self._last_refill = now
    
    def acquire(self, tokens: int = 1, timeout: Optional[float] = None) -> bool:
        """Acquire tokens from the bucket.
        
        Blocks until tokens are available or timeout is reached.
        
        Args:
            tokens: Number of tokens to acquire (default: 1)
            timeout: Maximum time to wait in seconds (None = wait forever)
            
        Returns:
            True if tokens were acquired, False if timeout was reached
            
        Raises:
            ValueError: If tokens is not positive
        """
        if tokens <= 0:
            raise ValueError("tokens must be positive")
        
        start_time = time.time()
        
        while True:
            with self._lock:
                # Refill tokens based on elapsed time
                self._refill_tokens()
                
                # Check if we have enough tokens
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return True
                
                # Calculate wait time until we have enough tokens
                tokens_needed = tokens - self._tokens
                wait_time = tokens_needed / self.refill_rate
            
            # Check timeout
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    return False
                # Adjust wait time to not exceed timeout
                wait_time = min(wait_time, timeout - elapsed)
            
            # Sleep for the calculated wait time
            time.sleep(wait_time)
    
    def try_acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens without blocking.
        
        Args:
            tokens: Number of tokens to acquire (default: 1)
            
        Returns:
            True if tokens were acquired, False otherwise
            
        Raises:
            ValueError: If tokens is not positive
        """
        if tokens <= 0:
            raise ValueError("tokens must be positive")
        
        with self._lock:
            # Refill tokens based on elapsed time
            self._refill_tokens()
            
            # Check if we have enough tokens
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            
            return False
    
    def get_available_tokens(self) -> float:
        """Get the current number of available tokens.
        
        Returns:
            Current number of tokens in the bucket
        """
        with self._lock:
            self._refill_tokens()
            return self._tokens
    
    def get_wait_time(self, tokens: int = 1) -> float:
        """Calculate wait time until tokens are available.
        
        Args:
            tokens: Number of tokens needed (default: 1)
            
        Returns:
            Wait time in seconds (0 if tokens are available now)
        """
        with self._lock:
            self._refill_tokens()
            
            if self._tokens >= tokens:
                return 0.0
            
            tokens_needed = tokens - self._tokens
            return tokens_needed / self.refill_rate
    
    def reset(self) -> None:
        """Reset the rate limiter to initial state (full burst capacity)."""
        with self._lock:
            self._tokens = float(self.burst_capacity)
            self._last_refill = time.time()

# Made with Bob
