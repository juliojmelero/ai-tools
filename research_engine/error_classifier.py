from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone
from email.utils import parsedate_to_datetime
from math import isfinite
from time import time
from typing import Callable

from research_engine.search_models import ProviderExecutionError, RetryPolicy


@dataclass(frozen=True, slots=True)
class RetryDecision:
    retryable: bool
    error: ProviderExecutionError
    http_status: int | None = None
    retry_after_seconds: float | None = None


class ErrorClassifier:
    """Converts provider-independent transient failures into retry decisions."""

    def __init__(self, *, wall_clock: Callable[[], float] = time) -> None:
        self._wall_clock = wall_clock

    def classify(self, exc: Exception, policy: RetryPolicy) -> RetryDecision:
        status = self._http_status(exc)
        retryable = (
            isinstance(exc, policy.retryable_exception_types)
            or "timeout" in type(exc).__name__.lower()
            or status in policy.retryable_statuses
        )
        code = "provider_transient_failure" if retryable else "provider_execution_failed"
        if status is not None:
            code = "provider_http_error"
        error = ProviderExecutionError(
            code=code,
            message=str(exc) or type(exc).__name__,
            error_type=type(exc).__name__,
            retryable=retryable,
        )
        return RetryDecision(
            retryable=retryable,
            error=error,
            http_status=status,
            retry_after_seconds=self._retry_after_seconds(exc),
        )

    def _retry_after_seconds(self, exc: Exception) -> float | None:
        response = getattr(exc, "response", None)
        candidates = (
            getattr(exc, "retry_after", None),
            self._header_value(getattr(response, "headers", None)),
            self._header_value(getattr(exc, "headers", None)),
        )
        for candidate in candidates:
            parsed = self._parse_retry_after(candidate)
            if parsed is not None:
                return parsed
        return None

    @staticmethod
    def _header_value(headers: object) -> object | None:
        try:
            return headers["Retry-After"]  # type: ignore[index]
        except (KeyError, TypeError, AttributeError):
            return None

    def _parse_retry_after(self, value: object) -> float | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            seconds = float(value)
            return seconds if isfinite(seconds) and seconds >= 0 else None
        if not isinstance(value, str):
            return None

        stripped = value.strip()
        if not stripped:
            return None
        try:
            seconds = float(stripped)
        except ValueError:
            try:
                parsed = parsedate_to_datetime(stripped)
                if parsed is None:
                    return None
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return max(0.0, parsed.timestamp() - self._wall_clock())
            except (TypeError, ValueError, OverflowError):
                return None
        return seconds if isfinite(seconds) and seconds >= 0 else None

    @staticmethod
    def _http_status(exc: Exception) -> int | None:
        for candidate in (
            getattr(exc, "status_code", None),
            getattr(exc, "status", None),
            getattr(getattr(exc, "response", None), "status_code", None),
        ):
            if isinstance(candidate, int) and not isinstance(candidate, bool):
                return candidate
        return None
