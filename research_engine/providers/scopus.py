import os
import json
import requests

from research_engine.base_provider import BaseProvider
from research_config.providers import get_api_key, get_provider
from research_models.converters import scopus_to_publication
from research_models.publication import publications_response


def _scopus_config():
    provider = get_provider("scopus")

    api_key = get_api_key("scopus") or os.getenv("SCOPUS_API_KEY")
    if not api_key:
        raise RuntimeError("Scopus API key not configured")

    base_url = (
        provider.get("base_url")
        if provider and provider.get("base_url")
        else "https://api.elsevier.com/content/search/scopus"
    )

    extra_config = {}
    if provider and provider.get("extra_config"):
        try:
            extra_config = json.loads(provider["extra_config"])
        except Exception:
            extra_config = {}

    inst_token = extra_config.get("inst_token") or os.getenv("SCOPUS_INST_TOKEN")

    return api_key, base_url, inst_token


class ScopusProvider(BaseProvider):

    id = "scopus"
    name = "Scopus"

    def search(
        self,
        query: str,
        max_results: int = 10,
        from_year: int | None = None,
        until_year: int | None = None,
    ) -> dict:
        api_key, base_url, inst_token = _scopus_config()

        headers = {
            "X-ELS-APIKey": api_key,
            "Accept": "application/json",
        }

        if inst_token:
            headers["X-ELS-Insttoken"] = inst_token

        params = {
            "query": query,
            "count": max_results,
            "sort": "-coverDate",
        }

        if from_year is not None:
            params["date"] = f"{from_year}-"

        if until_year is not None and from_year is not None:
            params["date"] = f"{from_year}-{until_year}"

        r = requests.get(
            base_url,
            headers=headers,
            params=params,
            timeout=30,
        )
        r.raise_for_status()

        entries = (
            r.json()
            .get("search-results", {})
            .get("entry", [])
        )

        publications = [
            scopus_to_publication(item)
            for item in entries
        ]

        return publications_response(
            provider="scopus",
            query=query,
            publications=publications,
        )
