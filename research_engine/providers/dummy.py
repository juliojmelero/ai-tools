from research_engine.base_provider import BaseProvider


class DummyProvider(BaseProvider):

    id = "dummy"
    name = "Dummy"

    def search(
        self,
        query,
        max_results=10,
        from_year=None,
        until_year=None,
    ):
        return {
            "provider": "dummy",
            "query": query,
            "count": 0,
            "results": [],
        }
