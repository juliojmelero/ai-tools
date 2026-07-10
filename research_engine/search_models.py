from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import asdict, dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any

from research_engine.rate_limiter import RateLimitPolicy


SUPPORTED_SORT_MODES = frozenset({
    "relevance",
    "score",
    "none",
    "citations",
    "year_desc",
    "year_asc",
    "title",
    "provider",
})


class ProviderStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class SearchRequest:
    query: str
    providers: tuple[str, ...] | None = None
    max_results: int = 20
    from_year: int | None = None
    until_year: int | None = None
    sort_mode: str = "relevance"

    def __post_init__(self) -> None:
        query = self.query.strip() if isinstance(self.query, str) else ""
        if not query:
            raise ValueError("query must be a non-blank string")
        object.__setattr__(self, "query", query)

        if (
            isinstance(self.max_results, bool)
            or not isinstance(self.max_results, int)
            or self.max_results <= 0
        ):
            raise ValueError("max_results must be greater than 0")

        if (
            self.from_year is not None
            and self.until_year is not None
            and self.from_year > self.until_year
        ):
            raise ValueError("from_year must be less than or equal to until_year")

        if self.providers is not None:
            if isinstance(self.providers, (str, bytes)):
                raise ValueError("providers must be a non-empty sequence of provider identifiers")

            providers = tuple(self.providers)
            if not providers:
                raise ValueError("providers must not be empty; use None for all enabled providers")

            invalid = [p for p in providers if not isinstance(p, str) or not p.strip()]
            if invalid:
                raise ValueError("provider identifiers must be non-blank strings")

            providers = tuple(p.strip() for p in providers)
            duplicates = sorted({p for p in providers if providers.count(p) > 1})
            if duplicates:
                raise ValueError(f"duplicate provider identifiers: {', '.join(duplicates)}")
            object.__setattr__(self, "providers", providers)

        if self.sort_mode not in SUPPORTED_SORT_MODES:
            supported = ", ".join(sorted(SUPPORTED_SORT_MODES))
            raise ValueError(f"unsupported sort_mode '{self.sort_mode}'; expected one of: {supported}")


@dataclass(frozen=True, slots=True)
class ProviderExecutionError:
    code: str
    message: str
    error_type: str
    retryable: bool = False
    http_status: int | None = None


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 3
    initial_backoff: float = 0.1
    backoff_multiplier: float = 2.0
    max_backoff: float = 5.0
    jitter: float = 0.0
    minimum_attempt_budget: float = 0.001
    retryable_statuses: frozenset[int] = frozenset({408, 429, 500, 502, 503, 504})
    retryable_exception_types: tuple[type[Exception], ...] = (
        ConnectionError,
        TimeoutError,
    )

    def __post_init__(self) -> None:
        if isinstance(self.max_attempts, bool) or not isinstance(self.max_attempts, int):
            raise TypeError("max_attempts must be an integer")
        if self.max_attempts <= 0:
            raise ValueError("max_attempts must be greater than 0")
        for name in (
            "initial_backoff", "max_backoff", "jitter", "minimum_attempt_budget"
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be a number")
            if value < 0:
                raise ValueError(f"{name} must be greater than or equal to 0")
        if (
            isinstance(self.backoff_multiplier, bool)
            or not isinstance(self.backoff_multiplier, (int, float))
        ):
            raise TypeError("backoff_multiplier must be a number")
        if self.backoff_multiplier <= 0:
            raise ValueError("backoff_multiplier must be greater than 0")
        if not all(isinstance(status, int) for status in self.retryable_statuses):
            raise TypeError("retryable_statuses must contain integers")
        if not all(
            isinstance(exception_type, type)
            and issubclass(exception_type, Exception)
            for exception_type in self.retryable_exception_types
        ):
            raise TypeError("retryable_exception_types must contain exception types")
        object.__setattr__(self, "retryable_statuses", frozenset(self.retryable_statuses))
        object.__setattr__(
            self, "retryable_exception_types", tuple(self.retryable_exception_types)
        )
        if self.minimum_attempt_budget <= 0:
            raise ValueError("minimum_attempt_budget must be greater than 0")


@dataclass(frozen=True, slots=True)
class ProviderAttempt:
    attempt_number: int
    started_at: float
    elapsed_ms: int
    status: ProviderStatus
    error: ProviderExecutionError | None = None
    scheduled_backoff: float | None = None


@dataclass(frozen=True, slots=True)
class ExecutionPolicy:
    default_provider_timeout: float = 30.0
    overall_timeout: float | None = None
    max_workers: int = 8
    retry_policy: RetryPolicy = RetryPolicy()
    default_rate_limit_policy: RateLimitPolicy | None = None
    provider_rate_limit_policies: Mapping[str, RateLimitPolicy] | None = None

    def __post_init__(self) -> None:
        if (
            isinstance(self.default_provider_timeout, bool)
            or not isinstance(self.default_provider_timeout, (int, float))
            or self.default_provider_timeout <= 0
        ):
            raise ValueError("default_provider_timeout must be greater than 0")
        if (
            self.overall_timeout is not None
            and (
                isinstance(self.overall_timeout, bool)
                or not isinstance(self.overall_timeout, (int, float))
                or self.overall_timeout <= 0
            )
        ):
            raise ValueError("overall_timeout must be greater than 0 when provided")
        if isinstance(self.max_workers, bool) or not isinstance(self.max_workers, int):
            raise TypeError("max_workers must be an integer")
        if self.max_workers <= 0:
            raise ValueError("max_workers must be greater than 0")
        if not isinstance(self.retry_policy, RetryPolicy):
            raise TypeError("retry_policy must be a RetryPolicy")
        if (
            self.default_rate_limit_policy is not None
            and not isinstance(self.default_rate_limit_policy, RateLimitPolicy)
        ):
            raise TypeError("default_rate_limit_policy must be a RateLimitPolicy")
        policies = dict(self.provider_rate_limit_policies or {})
        for provider_id, policy in policies.items():
            if not isinstance(provider_id, str) or not provider_id.strip():
                raise ValueError("rate limit policy provider IDs must be non-blank strings")
            if not isinstance(policy, RateLimitPolicy):
                raise TypeError("provider rate limit policies must be RateLimitPolicy values")
        object.__setattr__(
            self,
            "provider_rate_limit_policies",
            MappingProxyType(policies),
        )


@dataclass(frozen=True, slots=True)
class ProviderDeadline:
    timeout_seconds: float
    expires_at: float
    limited_by_overall_timeout: bool = False


@dataclass(frozen=True, slots=True)
class ProviderRequest:
    provider_id: str
    original_query: str
    planned_query: str
    max_results: int
    from_year: int | None
    until_year: int | None
    ordinal: int
    provider: Any | None = None
    preparation_error: ProviderExecutionError | None = None
    deadline: ProviderDeadline | None = None


@dataclass(frozen=True, slots=True)
class ProviderOutcome:
    provider_id: str
    status: ProviderStatus
    original_query: str
    planned_query: str
    records: tuple[dict[str, Any], ...]
    attempt_count: int
    elapsed_ms: int
    error: ProviderExecutionError | None
    ordinal: int
    deadline: ProviderDeadline | None = None
    attempts: tuple[ProviderAttempt, ...] = ()

    @property
    def attempt_history(self) -> tuple[ProviderAttempt, ...]:
        return self.attempts

    @property
    def final_error(self) -> ProviderExecutionError | None:
        return self.error

    @property
    def final_status(self) -> ProviderStatus:
        return self.status

    @property
    def successful(self) -> bool:
        return self.status is ProviderStatus.SUCCESS


@dataclass(frozen=True, slots=True)
class SearchResult(Mapping[str, Any]):
    query: str
    providers: tuple[str, ...]
    publications: tuple[dict[str, Any], ...]
    provider_outcomes: tuple[ProviderOutcome, ...]
    successful_providers: tuple[str, ...]
    failed_providers: tuple[str, ...]
    timed_out_providers: tuple[str, ...]
    cancelled_providers: tuple[str, ...]
    partial: bool
    raw_count: int
    final_count: int
    sort_mode: str
    errors: Mapping[str, str]
    planned_queries: Mapping[str, str]
    duplicates_removed: int

    @property
    def results(self) -> tuple[dict[str, Any], ...]:
        return self.publications

    @property
    def count(self) -> int:
        return self.final_count

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "providers": list(self.providers),
            "publications": list(self.publications),
            "results": list(self.publications),
            "provider_outcomes": [asdict(outcome) for outcome in self.provider_outcomes],
            "successful_providers": list(self.successful_providers),
            "failed_providers": list(self.failed_providers),
            "timed_out_providers": list(self.timed_out_providers),
            "cancelled_providers": list(self.cancelled_providers),
            "partial": self.partial,
            "raw_count": self.raw_count,
            "final_count": self.final_count,
            "count": self.final_count,
            "sort_mode": self.sort_mode,
            "errors": dict(self.errors),
            "planned_queries": dict(self.planned_queries),
            "duplicates_removed": self.duplicates_removed,
        }

    def __getitem__(self, key: str) -> Any:
        return self.to_dict()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.to_dict())

    def __len__(self) -> int:
        return len(self.to_dict())
