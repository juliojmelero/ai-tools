"""Lightweight, in-process metrics primitives.

The collector deliberately has no reporting or transport concerns.  Callers
record values on the hot path and obtain an immutable point-in-time snapshot
when they need to inspect them.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from threading import Lock
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True, slots=True)
class Counter:
    """An immutable counter value in a :class:`MetricsSnapshot`."""

    value: int


@dataclass(frozen=True, slots=True)
class Histogram:
    """An immutable aggregate of observed numeric values."""

    count: int
    sum: float
    min: float | None
    max: float | None


@dataclass(frozen=True, slots=True)
class MetricsSnapshot:
    """An immutable, consistent-per-metric view of collected metrics."""

    counters: Mapping[str, Counter]
    histograms: Mapping[str, Histogram]


class _CounterValue:
    __slots__ = ("_lock", "_value")

    def __init__(self) -> None:
        self._lock = Lock()
        self._value = 0

    def increment(self, value: int) -> None:
        with self._lock:
            self._value += value

    def snapshot(self) -> Counter:
        with self._lock:
            return Counter(self._value)


class _HistogramValue:
    __slots__ = ("_lock", "_count", "_sum", "_min", "_max")

    def __init__(self) -> None:
        self._lock = Lock()
        self._count = 0
        self._sum = 0.0
        self._min: float | None = None
        self._max: float | None = None

    def observe(self, value: float) -> None:
        with self._lock:
            self._count += 1
            self._sum += value
            self._min = value if self._min is None else min(self._min, value)
            self._max = value if self._max is None else max(self._max, value)

    def snapshot(self) -> Histogram:
        with self._lock:
            return Histogram(self._count, self._sum, self._min, self._max)


class MetricsCollector:
    """Thread-safe registry of named counters and histograms.

    The registry lock is only held while a metric is first created or while
    copying the registry for a snapshot.  Updates take only the individual
    metric's lock, keeping unrelated metric updates independent.
    """

    __slots__ = ("_lock", "_counters", "_histograms")

    def __init__(self) -> None:
        self._lock = Lock()
        self._counters: dict[str, _CounterValue] = {}
        self._histograms: dict[str, _HistogramValue] = {}

    def increment(self, name: str, value: int = 1) -> None:
        """Increase the named counter by a non-negative integer."""
        self._validate_name(name)
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("counter value must be an integer")
        if value < 0:
            raise ValueError("counter value must be non-negative")
        metric = self._counter_for(name)
        metric.increment(value)

    def observe(self, name: str, value: float) -> None:
        """Add a finite numeric observation to the named histogram."""
        self._validate_name(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("histogram value must be a number")
        numeric_value = float(value)
        if not isfinite(numeric_value):
            raise ValueError("histogram value must be finite")
        metric = self._histogram_for(name)
        metric.observe(numeric_value)

    def snapshot(self) -> MetricsSnapshot:
        """Return immutable metric values without exposing collector state."""
        # Registry dictionaries are copy-on-write.  Taking these references is
        # therefore safe without a registry-wide lock on the read path.
        counters = self._counters
        histograms = self._histograms
        return MetricsSnapshot(
            counters=MappingProxyType({
                name: metric.snapshot() for name, metric in counters.items()
            }),
            histograms=MappingProxyType({
                name: metric.snapshot() for name, metric in histograms.items()
            }),
        )

    def _counter_for(self, name: str) -> _CounterValue:
        metric = self._counters.get(name)
        if metric is not None:
            return metric
        with self._lock:
            metric = self._counters.get(name)
            if metric is None:
                metric = _CounterValue()
                counters = self._counters.copy()
                counters[name] = metric
                self._counters = counters
            return metric

    def _histogram_for(self, name: str) -> _HistogramValue:
        metric = self._histograms.get(name)
        if metric is not None:
            return metric
        with self._lock:
            metric = self._histograms.get(name)
            if metric is None:
                metric = _HistogramValue()
                histograms = self._histograms.copy()
                histograms[name] = metric
                self._histograms = histograms
            return metric

    @staticmethod
    def _validate_name(name: str) -> None:
        if not isinstance(name, str):
            raise TypeError("metric name must be a string")
        if not name:
            raise ValueError("metric name must not be empty")


class NullMetricsCollector:
    """No-op collector for callers that do not enable observability.

    All state, including the empty snapshot, is class-level so recording and
    snapshot calls allocate nothing after construction.
    """

    __slots__ = ()
    _EMPTY_SNAPSHOT = MetricsSnapshot(MappingProxyType({}), MappingProxyType({}))

    def increment(self, name: str, value: int = 1) -> None:
        return None

    def observe(self, name: str, value: float) -> None:
        return None

    def snapshot(self) -> MetricsSnapshot:
        return self._EMPTY_SNAPSHOT
