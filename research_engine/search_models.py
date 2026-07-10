from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


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
