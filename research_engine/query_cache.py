"""Thread-safe, in-memory cache for completed search results."""

from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass, field, replace
from math import isfinite
from threading import RLock
from time import monotonic
from types import MappingProxyType
from typing import Callable

from research_engine.search_models import SearchResult


_configuration_version = 0
_configuration_version_lock = RLock()


def _get_configuration_version() -> int:
    """Return the process-local version of provider configuration."""
    with _configuration_version_lock:
        return _configuration_version


def _increment_configuration_version() -> None:
    """Invalidate cache keys after a provider configuration mutation."""
    global _configuration_version
    with _configuration_version_lock:
        _configuration_version += 1


@dataclass(frozen=True, slots=True)
class CacheKey:
    """The complete set of inputs that can affect a search result."""

    query: str
    providers: tuple[str, ...]
    max_results: int
    from_year: int | None
    until_year: int | None
    sort_mode: str
    configuration_version: int = field(default_factory=_get_configuration_version)

    def __post_init__(self) -> None:
        """Canonicalize provider IDs so the key remains hashable and immutable."""
        if isinstance(self.providers, (str, bytes)):
            raise TypeError("providers must be a sequence of provider identifiers")
        providers = tuple(self.providers)
        if not all(isinstance(provider, str) for provider in providers):
            raise TypeError("providers must contain provider identifier strings")
        object.__setattr__(self, "providers", providers)


@dataclass(frozen=True, slots=True)
class _CacheEntry:
    result: SearchResult
    expires_at: float


class QueryCache:
    """Bounded LRU cache with monotonic-time expiry.

    ``clock`` is injectable for deterministic tests.  It is intentionally an
    implementation detail: callers normally only need ``max_entries`` and
    ``ttl_seconds``.
    """

    def __init__(
        self,
        max_entries: int = 128,
        ttl_seconds: float = 300.0,
        *,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if isinstance(max_entries, bool) or not isinstance(max_entries, int):
            raise TypeError("max_entries must be an integer")
        if max_entries <= 0:
            raise ValueError("max_entries must be greater than 0")
        if (
            isinstance(ttl_seconds, bool)
            or not isinstance(ttl_seconds, (int, float))
        ):
            raise TypeError("ttl_seconds must be a number")
        if not isfinite(ttl_seconds) or ttl_seconds < 0:
            raise ValueError("ttl_seconds must be greater than or equal to 0")
        if not callable(clock):
            raise TypeError("clock must be callable")

        self.max_entries = max_entries
        self.ttl_seconds = float(ttl_seconds)
        self._clock = clock
        self._entries: OrderedDict[CacheKey, _CacheEntry] = OrderedDict()
        self._lock = RLock()

    def get(self, key: CacheKey) -> SearchResult | None:
        """Return a live value and mark it as most recently used."""
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if self._clock() >= entry.expires_at:
                del self._entries[key]
                return None
            self._entries.move_to_end(key)
            return self._copy_result(entry.result)

    def set(self, key: CacheKey, result: SearchResult) -> None:
        """Store a completed result, evicting the least recently used entry."""
        if not self._is_complete_success(result):
            return
        with self._lock:
            self._entries[key] = _CacheEntry(
                result=self._copy_result(result),
                expires_at=self._clock() + self.ttl_seconds,
            )
            self._entries.move_to_end(key)
            while len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)

    @staticmethod
    def _is_complete_success(result: SearchResult) -> bool:
        return (
            bool(result.providers)
            and result.successful_providers == result.providers
            and not result.failed_providers
            and not result.timed_out_providers
            and not result.cancelled_providers
            and not result.partial
        )

    @staticmethod
    def _copy_result(result: SearchResult) -> SearchResult:
        return SearchResult(
            query=result.query,
            providers=result.providers,
            publications=tuple(deepcopy(publication) for publication in result.publications),
            provider_outcomes=tuple(
                replace(
                    outcome,
                    records=tuple(deepcopy(record) for record in outcome.records),
                )
                for outcome in result.provider_outcomes
            ),
            successful_providers=result.successful_providers,
            failed_providers=result.failed_providers,
            timed_out_providers=result.timed_out_providers,
            cancelled_providers=result.cancelled_providers,
            partial=result.partial,
            raw_count=result.raw_count,
            final_count=result.final_count,
            sort_mode=result.sort_mode,
            errors=MappingProxyType(dict(result.errors)),
            planned_queries=MappingProxyType(dict(result.planned_queries)),
            duplicates_removed=result.duplicates_removed,
        )
