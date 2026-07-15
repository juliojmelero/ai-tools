from __future__ import annotations

import warnings
from collections.abc import Sequence
from types import MappingProxyType

from research_engine.deduplicator import Deduplicator
from research_engine.fusion_engine import FusionEngine
from research_engine.provider_manager import ProviderManager
from research_engine.provider_registry import get_registry
from research_engine.query_cache import CacheKey, QueryCache
from research_engine.query_planner import QueryPlanner
from research_engine.ranking import Ranker
from research_engine.search_executor import SearchExecutor
from research_engine.search_models import (
    ProviderExecutionError,
    ProviderOutcome,
    ProviderRequest,
    ProviderStatus,
    SearchRequest,
    SearchResult,
)


class SearchEngine:
    """Public facade for the scientific search pipeline."""

    def __init__(
        self,
        provider_manager=None,
        provider_registry=None,
        query_planner=None,
        executor=None,
        deduplicator=None,
        fusion_engine: FusionEngine | None = None,
        ranker=None,
    ):
        self.pm = provider_manager or ProviderManager()
        self.registry = provider_registry or get_registry()
        self.query_planner = query_planner or QueryPlanner()
        self.executor = executor or SearchExecutor()
        self.deduplicator = deduplicator or Deduplicator()
        self.fusion_engine = fusion_engine or FusionEngine()
        self.ranker = ranker or Ranker()
        self.cache = QueryCache()

    def search(
        self,
        query: str,
        providers: Sequence[str] | None = None,
        max_results: int = 20,
        from_year: int | None = None,
        until_year: int | None = None,
        sort_mode: str = "relevance",
    ) -> SearchResult:
        request = SearchRequest(
            query=query,
            providers=None if providers is None else tuple(providers),
            max_results=max_results,
            from_year=from_year,
            until_year=until_year,
            sort_mode=sort_mode,
        )
        selected = self._select_providers(request)
        cache_key = CacheKey(
            query=request.query,
            providers=selected,
            max_results=request.max_results,
            from_year=request.from_year,
            until_year=request.until_year,
            sort_mode=request.sort_mode,
        )
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        provider_requests = tuple(
            self._prepare_provider_request(request, provider_id, ordinal)
            for ordinal, provider_id in enumerate(selected)
        )
        outcomes = self.executor.execute(provider_requests)

        raw_records = [
            dict(record)
            for outcome in outcomes
            if outcome.status is ProviderStatus.SUCCESS
            for record in outcome.records
        ]
        clusters = self.deduplicator.cluster(raw_records)
        fused = []
        for records in clusters.values():
            publication = None
            for record in records:
                publication = self.fusion_engine.merge(publication, record)
            fused.append(publication)

        rank_sort_mode = "score" if request.sort_mode == "relevance" else request.sort_mode
        ranked = self.ranker.rank(fused, sort_mode=rank_sort_mode)
        publications = tuple(ranked[:request.max_results])

        successful = self._providers_with_status(outcomes, ProviderStatus.SUCCESS)
        failed = self._providers_with_status(outcomes, ProviderStatus.FAILED)
        timed_out = self._providers_with_status(outcomes, ProviderStatus.TIMED_OUT)
        cancelled = self._providers_with_status(outcomes, ProviderStatus.CANCELLED)
        errors = MappingProxyType({
            outcome.provider_id: outcome.error.message
            for outcome in outcomes
            if outcome.error is not None
        })
        planned_queries = MappingProxyType({
            outcome.provider_id: outcome.planned_query
            for outcome in outcomes
        })

        result = SearchResult(
            query=request.query,
            providers=selected,
            publications=publications,
            provider_outcomes=outcomes,
            successful_providers=successful,
            failed_providers=failed,
            timed_out_providers=timed_out,
            cancelled_providers=cancelled,
            partial=bool(timed_out or (successful and (failed or cancelled))),
            raw_count=len(raw_records),
            final_count=len(publications),
            sort_mode=request.sort_mode,
            errors=errors,
            planned_queries=planned_queries,
            duplicates_removed=len(raw_records) - len(clusters),
        )
        if not result.partial:
            self.cache.set(cache_key, result)
        return result

    def search_all(
        self,
        query: str,
        max_results: int = 20,
        from_year: int | None = None,
        until_year: int | None = None,
        providers: Sequence[str] | None = None,
        sort_mode: str = "score",
    ) -> SearchResult:
        warnings.warn(
            "SearchEngine.search_all() is deprecated; use SearchEngine.search()",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.search(
            query=query,
            providers=providers,
            max_results=max_results,
            from_year=from_year,
            until_year=until_year,
            sort_mode=sort_mode,
        )

    def _select_providers(self, request: SearchRequest) -> tuple[str, ...]:
        if request.providers is not None:
            return request.providers

        return tuple(provider["id"] for provider in self.pm.list_enabled())

    def _prepare_provider_request(
        self,
        request: SearchRequest,
        provider_id: str,
        ordinal: int,
    ) -> ProviderRequest:
        implementation = self.registry.get_optional(provider_id)
        configuration = self.pm.get(provider_id)
        error = None
        planned_query = request.query

        if configuration is None:
            error = ProviderExecutionError(
                code="unknown_provider",
                message=f"Unknown provider: {provider_id}",
                error_type="ProviderConfigurationError",
            )
        elif not configuration.get("enabled"):
            error = ProviderExecutionError(
                code="provider_disabled",
                message=f"Provider '{provider_id}' is disabled",
                error_type="ProviderDisabledError",
            )
        elif implementation is None:
            error = ProviderExecutionError(
                code="provider_implementation_unavailable",
                message=f"Provider implementation is unavailable: {provider_id}",
                error_type="ProviderImplementationError",
            )
        else:
            try:
                planned_query = self.query_planner.plan(
                    query=request.query,
                    provider=provider_id,
                )
            except Exception as exc:
                error = ProviderExecutionError(
                    code="query_planning_failed",
                    message=str(exc) or type(exc).__name__,
                    error_type=type(exc).__name__,
                )

        return ProviderRequest(
            provider_id=provider_id,
            original_query=request.query,
            planned_query=planned_query,
            max_results=request.max_results,
            from_year=request.from_year,
            until_year=request.until_year,
            ordinal=ordinal,
            provider=implementation,
            preparation_error=error,
        )

    @staticmethod
    def _providers_with_status(
        outcomes: tuple[ProviderOutcome, ...],
        status: ProviderStatus,
    ) -> tuple[str, ...]:
        return tuple(
            outcome.provider_id
            for outcome in outcomes
            if outcome.status is status
        )
