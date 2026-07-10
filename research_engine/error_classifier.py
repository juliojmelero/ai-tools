from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone
from email.utils import parsedate_to_datetime
from inspect import Signature, signature
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
            code = f"provider_http_{status}"
        error = ProviderExecutionError(
            code=code,
            message=str(exc) or type(exc).__name__,
            error_type=type(exc).__name__,
            retryable=retryable,
            http_status=status,
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

    @classmethod
    def _http_status(cls, exc: Exception) -> int | None:
        names = ("status_code", "http_status", "status", "code")
        for name in names:
            status = cls._status_value(exc, name)
            if status is not None:
                return status

        response = cls._safe_attribute(exc, "response")
        for name in ("status_code", "status", "code"):
            status = cls._status_value(response, name)
            if status is not None:
                return status
        return None

    @classmethod
    def _status_value(cls, owner: object, name: str) -> int | None:
        candidate = cls._safe_attribute(owner, name)
        if callable(candidate):
            try:
                accessor_signature: Signature = signature(candidate)
                accessor_signature.bind()
            except (TypeError, ValueError):
                return None
            try:
                candidate = candidate()
            except Exception:
                return None

        if isinstance(candidate, bool):
            return None
        if isinstance(candidate, int):
            status = candidate
        elif isinstance(candidate, str):
            stripped = candidate.strip()
            if not stripped.isdecimal():
                return None
            status = int(stripped)
        else:
            return None
        return status if 100 <= status <= 599 else None

    @staticmethod
    def _safe_attribute(owner: object, name: str) -> object | None:
        try:
            return getattr(owner, name, None)
        except Exception:
            return None
