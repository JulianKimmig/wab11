"""
Rate limiting for WAB11 write operations.

Protects the heat pump controller from excessive write operations
that could cause issues or wear.
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict


class RateLimiter:
    """
    Rate limits write operations to protect the heat pump controller.

    Default limits:
    - Max 10 writes per minute globally
    - Max 2 writes per register per minute
    - Min 1 second cooldown between writes to same register

    The rate limiter is non-blocking by default - it will wait
    until the rate limit allows the operation to proceed.

    Usage:
        limiter = RateLimiter()
        await limiter.acquire("hk1_setpoint_comfort")  # Wait if needed
        # ... perform write ...
    """

    def __init__(
        self,
        global_limit: int = 10,
        per_register_limit: int = 2,
        cooldown: float = 1.0,
        window: float = 60.0,
    ) -> None:
        """
        Initialize rate limiter.

        Args:
            global_limit: Maximum writes per window globally
            per_register_limit: Maximum writes per register per window
            cooldown: Minimum seconds between writes to same register
            window: Time window in seconds for rate limiting
        """
        self._global_limit = global_limit
        self._per_register_limit = per_register_limit
        self._cooldown = cooldown
        self._window = window

        self._global_writes: list[float] = []
        self._register_writes: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    @property
    def global_limit(self) -> int:
        """Get the global write limit per window."""
        return self._global_limit

    @property
    def per_register_limit(self) -> int:
        """Get the per-register write limit per window."""
        return self._per_register_limit

    @property
    def cooldown(self) -> float:
        """Get the minimum cooldown between same-register writes."""
        return self._cooldown

    def _cleanup_old_writes(self, writes: list[float]) -> list[float]:
        """Remove writes older than the window."""
        cutoff = time.time() - self._window
        return [t for t in writes if t > cutoff]

    async def acquire(self, register_name: str) -> None:
        """
        Acquire permission to write to a register.

        This method will wait if necessary until the rate limit
        allows the write operation to proceed.

        Args:
            register_name: Name of the register to write
        """
        async with self._lock:
            now = time.time()

            # Clean up old entries
            self._global_writes = self._cleanup_old_writes(self._global_writes)
            self._register_writes[register_name] = self._cleanup_old_writes(
                self._register_writes[register_name]
            )

            # Check cooldown for same register
            if self._register_writes[register_name]:
                last_write = self._register_writes[register_name][-1]
                wait_time = self._cooldown - (now - last_write)
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                    now = time.time()

            # Check global limit
            while len(self._global_writes) >= self._global_limit:
                # Wait until oldest write expires
                oldest = self._global_writes[0]
                wait_time = self._window - (now - oldest) + 0.1
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                now = time.time()
                self._global_writes = self._cleanup_old_writes(self._global_writes)

            # Check per-register limit
            while len(self._register_writes[register_name]) >= self._per_register_limit:
                oldest = self._register_writes[register_name][0]
                wait_time = self._window - (now - oldest) + 0.1
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                now = time.time()
                self._register_writes[register_name] = self._cleanup_old_writes(
                    self._register_writes[register_name]
                )

            # Record write
            now = time.time()
            self._global_writes.append(now)
            self._register_writes[register_name].append(now)

    def get_wait_time(self, register_name: str) -> float:
        """
        Get the wait time before a write would be allowed.

        Args:
            register_name: Name of the register

        Returns:
            Seconds to wait (0 if write allowed immediately)
        """
        now = time.time()

        # Clean copies for calculation
        global_writes = self._cleanup_old_writes(self._global_writes.copy())
        register_writes = self._cleanup_old_writes(
            self._register_writes.get(register_name, []).copy()
        )

        wait_times = [0.0]

        # Cooldown check
        if register_writes:
            last_write = register_writes[-1]
            cooldown_wait = self._cooldown - (now - last_write)
            if cooldown_wait > 0:
                wait_times.append(cooldown_wait)

        # Global limit check
        if len(global_writes) >= self._global_limit:
            oldest = global_writes[0]
            global_wait = self._window - (now - oldest)
            if global_wait > 0:
                wait_times.append(global_wait)

        # Per-register limit check
        if len(register_writes) >= self._per_register_limit:
            oldest = register_writes[0]
            register_wait = self._window - (now - oldest)
            if register_wait > 0:
                wait_times.append(register_wait)

        return max(wait_times)

    def can_write_immediately(self, register_name: str) -> bool:
        """
        Check if a write can proceed without waiting.

        Args:
            register_name: Name of the register

        Returns:
            True if write can proceed immediately
        """
        return self.get_wait_time(register_name) <= 0

    def get_stats(self) -> dict:
        """
        Get current rate limiter statistics.

        Returns:
            Dictionary with current write counts and limits
        """
        global_writes = self._cleanup_old_writes(self._global_writes.copy())

        register_counts = {}
        for name, writes in self._register_writes.items():
            cleaned = self._cleanup_old_writes(writes.copy())
            if cleaned:
                register_counts[name] = len(cleaned)

        return {
            "global_writes": len(global_writes),
            "global_limit": self._global_limit,
            "per_register_limit": self._per_register_limit,
            "cooldown": self._cooldown,
            "window": self._window,
            "register_counts": register_counts,
        }

    def reset(self) -> None:
        """Reset all rate limiting counters."""
        self._global_writes.clear()
        self._register_writes.clear()
