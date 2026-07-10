from __future__ import annotations

from dataclasses import dataclass

from research_engine.search_models import ProviderExecutionError, RetryPolicy


@dataclass(frozen=True, slots=True)
class RetryDecision:
    retryable: bool
    error: ProviderExecutionError
    http_status: int | None = None


class ErrorClassifier:
    """Converts provider-independent transient failures into retry decisions."""

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
        return RetryDecision(retryable=retryable, error=error, http_status=status)

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
