from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from math import isfinite
from threading import Event, Lock
from time import monotonic, sleep
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from research_engine.search_models import ProviderDeadline


@dataclass(frozen=True, slots=True)
class RateLimitPolicy:
    requests_per_second: float
    burst_capacity: int

    def __post_init__(self) -> None:
        if (
            isinstance(self.requests_per_second, bool)
            or not isinstance(self.requests_per_second, (int, float))
            or not isfinite(self.requests_per_second)
            or self.requests_per_second <= 0
        ):
            raise ValueError("requests_per_second must be finite and greater than 0")
        if (
            isinstance(self.burst_capacity, bool)
            or not isinstance(self.burst_capacity, int)
        ):
            raise TypeError("burst_capacity must be an integer")
        if self.burst_capacity < 1:
            raise ValueError("burst_capacity must be greater than or equal to 1")


class RateLimiter(ABC):
    @abstractmethod
    def acquire(
        self,
        deadline: ProviderDeadline,
        terminal_state: Event,
    ) -> bool:
        """Return whether permission was acquired before execution became terminal."""


class TokenBucketRateLimiter(RateLimiter):
    """Thread-safe, lazily refilled token bucket."""

    def __init__(
        self,
        policy: RateLimitPolicy,
        *,
        clock: Callable[[], float] = monotonic,
        sleeper: Callable[[float], None] = sleep,
        max_sleep_seconds: float = 0.05,
    ) -> None:
        if not isinstance(policy, RateLimitPolicy):
            raise TypeError("policy must be a RateLimitPolicy")
        if max_sleep_seconds <= 0 or not isfinite(max_sleep_seconds):
            raise ValueError("max_sleep_seconds must be finite and greater than 0")
        self.policy = policy
        self._clock = clock
        self._sleeper = sleeper
        self._max_sleep_seconds = max_sleep_seconds
        self._tokens = float(policy.burst_capacity)
        self._last_refill = clock()
        self._lock = Lock()

    def acquire(
        self,
        deadline: ProviderDeadline,
        terminal_state: Event,
    ) -> bool:
        while True:
            if terminal_state.is_set():
                return False

            now = self._clock()
            if now >= deadline.expires_at:
                return False

            with self._lock:
                self._refill(now)
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return True
                seconds_to_token = (1.0 - self._tokens) / float(
                    self.policy.requests_per_second
                )

            wait_seconds = min(
                seconds_to_token,
                deadline.expires_at - now,
                self._max_sleep_seconds,
            )
            if wait_seconds <= 0:
                return False
            self._sleeper(wait_seconds)

    def _refill(self, now: float) -> None:
        elapsed = max(0.0, now - self._last_refill)
        if elapsed:
            self._tokens = min(
                float(self.policy.burst_capacity),
                self._tokens + elapsed * float(self.policy.requests_per_second),
            )
            self._last_refill = now


class RateLimiterRegistry:
    """Process-local registry keyed only by stable provider identifiers."""

    def __init__(
        self,
        default_policy: RateLimitPolicy | None = None,
        provider_policies: Mapping[str, RateLimitPolicy] | None = None,
        *,
        clock: Callable[[], float] = monotonic,
        sleeper: Callable[[float], None] = sleep,
        max_sleep_seconds: float = 0.05,
    ) -> None:
        self._default_policy = default_policy
        self._provider_policies = dict(provider_policies or {})
        self._clock = clock
        self._sleeper = sleeper
        self._max_sleep_seconds = max_sleep_seconds
        self._limiters: dict[str, TokenBucketRateLimiter] = {}
        self._cooldown_expires_at: dict[str, float] = {}
        self._lock = Lock()

    def apply_cooldown(self, provider_id: str, seconds: float) -> None:
        """Extend a provider's process-local cooldown using monotonic time."""
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
            raise TypeError("cooldown seconds must be a number")
        if not isfinite(seconds) or seconds < 0:
            raise ValueError("cooldown seconds must be finite and non-negative")
        expires_at = self._clock() + float(seconds)
        with self._lock:
            self._cooldown_expires_at[provider_id] = max(
                expires_at,
                self._cooldown_expires_at.get(provider_id, expires_at),
            )

    def wait_for_cooldown(
        self,
        provider_id: str,
        deadline: ProviderDeadline,
        terminal_state: Event,
    ) -> bool:
        """Wait without acquiring or consuming a token-bucket token."""
        while True:
            if terminal_state.is_set():
                return False
            now = self._clock()
            with self._lock:
                cooldown_expiry = self._cooldown_expires_at.get(provider_id, 0.0)
                if cooldown_expiry <= now:
                    self._cooldown_expires_at.pop(provider_id, None)
                    return True
            if now >= deadline.expires_at:
                return False
            wait_seconds = min(
                cooldown_expiry - now,
                deadline.expires_at - now,
                self._max_sleep_seconds,
            )
            if wait_seconds <= 0:
                return False
            self._sleeper(wait_seconds)

    def get(
        self,
        provider_id: str,
        policy: RateLimitPolicy | None = None,
    ) -> RateLimiter | None:
        effective_policy = policy
        if effective_policy is None:
            effective_policy = self._provider_policies.get(
                provider_id, self._default_policy
            )
        if effective_policy is None:
            return None

        with self._lock:
            limiter = self._limiters.get(provider_id)
            if limiter is None:
                limiter = TokenBucketRateLimiter(
                    effective_policy,
                    clock=self._clock,
                    sleeper=self._sleeper,
                    max_sleep_seconds=self._max_sleep_seconds,
                )
                self._limiters[provider_id] = limiter
            elif limiter.policy != effective_policy:
                raise ValueError(
                    f"provider '{provider_id}' already has a different rate limit policy"
                )
            return limiter


_SHARED_REGISTRY = RateLimiterRegistry()


def get_rate_limiter_registry() -> RateLimiterRegistry:
    return _SHARED_REGISTRY
