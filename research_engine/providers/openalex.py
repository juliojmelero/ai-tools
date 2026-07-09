import os
import json
import requests

from research_engine.base_provider import BaseProvider
from research_config.providers import get_provider
from research_models.converters import openalex_to_publication
from research_models.publication import publications_response


def _openalex_config():
    provider = get_provider("openalex")

    base_url = (
        provider.get("base_url")
        if provider and provider.get("base_url")
        else "https://api.openalex.org"
    )

    mailto = os.getenv("OPENALEX_MAILTO", "")

    if provider and provider.get("extra_config"):
        try:
            extra = json.loads(provider["extra_config"])
            mailto = extra.get("mailto") or mailto
        except Exception:
            pass

    return base_url, mailto


class OpenAlexProvider(BaseProvider):

    id = "openalex"
    name = "OpenAlex"

    def search(
        self,
        query: str,
        max_results: int = 10,
        from_year: int | None = None,
        until_year: int | None = None,
    ) -> dict:
        base_url, mailto = _openalex_config()

        filters = []

        if from_year is not None:
            filters.append(f"from_publication_date:{from_year}-01-01")

        if until_year is not None:
            filters.append(f"to_publication_date:{until_year}-12-31")

        params = {
            "search": query,
            "per-page": max_results,
            "sort": "relevance_score:desc",
        }

        if filters:
            params["filter"] = ",".join(filters)

        if mailto:
            params["mailto"] = mailto

        r = requests.get(
            f"{base_url}/works",
            params=params,
            timeout=30,
        )
        r.raise_for_status()

        items = r.json().get("results", [])

        publications = [
            openalex_to_publication(item)
            for item in items
        ]

        return publications_response(
            provider="openalex",
            query=query,
            publications=publications,
        )
