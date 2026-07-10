from __future__ import annotations

from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from time import monotonic
from typing import Any

from research_engine.search_models import (
    ProviderExecutionError,
    ProviderOutcome,
    ProviderRequest,
    ProviderStatus,
)


class InvalidProviderResponse(ValueError):
    pass


class SearchExecutor:
    """Bounded concurrent executor with one terminal outcome per request."""

    def __init__(self, max_workers: int = 8):
        if isinstance(max_workers, bool) or not isinstance(max_workers, int):
            raise TypeError("max_workers must be an integer")
        if max_workers <= 0:
            raise ValueError("max_workers must be greater than 0")
        self.max_workers = max_workers

    def execute(self, requests: Sequence[ProviderRequest]) -> tuple[ProviderOutcome, ...]:
        requests = tuple(requests)
        if not requests:
            return ()

        effective_workers = min(self.max_workers, len(requests))
        with ThreadPoolExecutor(max_workers=effective_workers) as executor:
            futures = [executor.submit(self._execute_one, request) for request in requests]
            return tuple(future.result() for future in futures)

    def _execute_one(self, request: ProviderRequest) -> ProviderOutcome:
        started = monotonic()

        if request.preparation_error is not None:
            return self._failed_outcome(
                request=request,
                error=request.preparation_error,
                attempt_count=0,
                started=started,
            )

        try:
            response = request.provider.search(
                query=request.planned_query,
                max_results=request.max_results,
                from_year=request.from_year,
                until_year=request.until_year,
            )
            records = self._validate_response(response, request.provider_id)
        except InvalidProviderResponse as exc:
            return self._failed_outcome(
                request=request,
                error=ProviderExecutionError(
                    code="invalid_provider_response",
                    message=str(exc),
                    error_type=type(exc).__name__,
                ),
                attempt_count=1,
                started=started,
            )
        except Exception as exc:
            return self._failed_outcome(
                request=request,
                error=ProviderExecutionError(
                    code="provider_execution_failed",
                    message=str(exc) or type(exc).__name__,
                    error_type=type(exc).__name__,
                ),
                attempt_count=1,
                started=started,
            )

        return ProviderOutcome(
            provider_id=request.provider_id,
            status=ProviderStatus.SUCCESS,
            original_query=request.original_query,
            planned_query=request.planned_query,
            records=records,
            attempt_count=1,
            elapsed_ms=self._elapsed_ms(started),
            error=None,
            ordinal=request.ordinal,
        )

    @staticmethod
    def _validate_response(
        response: Any,
        provider_id: str,
    ) -> tuple[dict[str, Any], ...]:
        if not isinstance(response, Mapping):
            raise InvalidProviderResponse("provider response must be a mapping")
        if "results" not in response:
            raise InvalidProviderResponse("provider response must contain 'results'")

        results = response["results"]
        if not isinstance(results, list):
            raise InvalidProviderResponse("provider response 'results' must be a list")

        normalized = []
        for index, record in enumerate(results):
            if not isinstance(record, Mapping):
                raise InvalidProviderResponse(
                    f"provider response result at index {index} must be a mapping"
                )
            copied = dict(record)
            if not copied.get("provider"):
                copied["provider"] = provider_id
            normalized.append(copied)

        return tuple(normalized)

    @staticmethod
    def _elapsed_ms(started: float) -> int:
        return max(0, round((monotonic() - started) * 1000))

    def _failed_outcome(
        self,
        request: ProviderRequest,
        error: ProviderExecutionError,
        attempt_count: int,
        started: float,
    ) -> ProviderOutcome:
        return ProviderOutcome(
            provider_id=request.provider_id,
            status=ProviderStatus.FAILED,
            original_query=request.original_query,
            planned_query=request.planned_query,
            records=(),
            attempt_count=attempt_count,
            elapsed_ms=self._elapsed_ms(started),
            error=error,
            ordinal=request.ordinal,
        )
