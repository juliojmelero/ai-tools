import os
import json
import requests

from research_engine.base_provider import BaseProvider
from research_config.providers import get_provider
from research_models.converters import crossref_to_publication
from research_models.publication import publications_response


def _crossref_config():
    provider = get_provider("crossref")

    base_url = (
        provider.get("base_url")
        if provider and provider.get("base_url")
        else "https://api.crossref.org"
    )

    mailto = os.getenv("CROSSREF_MAILTO", "")

    if provider and provider.get("extra_config"):
        try:
            extra = json.loads(provider["extra_config"])
            mailto = extra.get("mailto") or mailto
        except Exception:
            pass

    return base_url, mailto


class CrossrefProvider(BaseProvider):

    id = "crossref"
    name = "Crossref"

    def search(
        self,
        query: str,
        max_results: int = 10,
        from_year: int | None = None,
        until_year: int | None = None,
    ) -> dict:
        base_url, mailto = _crossref_config()

        params = {
            "query.bibliographic": query,
            "rows": max_results,
            "sort": "relevance",
            "order": "desc",
        }

        filters = []

        if from_year is not None:
            filters.append(f"from-pub-date:{from_year}")

        if until_year is not None:
            filters.append(f"until-pub-date:{until_year}")

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

        items = r.json().get("message", {}).get("items", [])

        publications = [
            crossref_to_publication(item)
            for item in items
        ]

        return publications_response(
            provider="crossref",
            query=query,
            publications=publications,
        )
