from research_engine.provider_manager import ProviderManager
from research_engine.provider_registry import get_provider, list_providers
from research_engine.deduplicator import Deduplicator
from research_engine.fusion_engine import FusionEngine
from research_engine.ranking import Ranker
from research_engine.query_planner import QueryPlanner


class SearchEngine:

    def __init__(self):
        self.pm = ProviderManager()
        self.deduplicator = Deduplicator()
        self.fusion = FusionEngine()
        self.ranker = Ranker()
        self.query_planner = QueryPlanner()

    def search(
        self,
        provider: str,
        query: str,
        max_results: int = 10,
        from_year: int | None = None,
        until_year: int | None = None,
    ):
        if not self.pm.exists(provider):
            raise ValueError(f"Unknown provider: {provider}")

        if not self.pm.enabled(provider):
            raise RuntimeError(f"Provider '{provider}' is disabled")

        planned_query = self.query_planner.plan(
            query=query,
            provider=provider,
        )

        engine = get_provider(provider)

        response = engine.search(
            query=planned_query,
            max_results=max_results,
            from_year=from_year,
            until_year=until_year,
        )

        if isinstance(response, dict):
            response["original_query"] = query
            response["planned_query"] = planned_query

        return response

    def search_all(
        self,
        query: str,
        max_results: int = 20,
        from_year: int | None = None,
        until_year: int | None = None,
        providers: list[str] | None = None,
        sort_mode: str = "score",
    ):
        selected = providers or [
            p.id
            for p in list_providers()
            if self.pm.enabled(p.id)
        ]

        raw_results = []
        errors = {}
        planned_queries = {}

        per_provider = max_results

        for provider_id in selected:
            try:
                response = self.search(
                    provider=provider_id,
                    query=query,
                    max_results=per_provider,
                    from_year=from_year,
                    until_year=until_year,
                )

                if isinstance(response, dict):
                    planned_queries[provider_id] = response.get("planned_query")
                    raw_results.extend(response.get("results", []))
                else:
                    errors[provider_id] = "Provider returned non-dict response"

            except Exception as e:
                errors[provider_id] = str(e)

        clusters = self.deduplicator.cluster(raw_results)
        fused = []

        for records in clusters.values():
            publication = None
            for record in records:
                publication = self.fusion.merge(publication, record)
            fused.append(publication)

        ranked = self.ranker.rank(fused, sort_mode=sort_mode)

        return {
            "query": query,
            "planned_queries": planned_queries,
            "providers": selected,
            "sort_mode": sort_mode,
            "raw_count": len(raw_results),
            "duplicates_removed": len(raw_results) - len(clusters),
            "count": min(len(ranked), max_results),
            "errors": errors,
            "results": ranked[:max_results],
        }
