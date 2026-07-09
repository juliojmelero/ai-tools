import os
import requests

from research_config.providers import get_api_key, get_provider


def _get_sciencedirect_config():
    provider = get_provider("sciencedirect")

    api_key = get_api_key("sciencedirect") or os.getenv("ELSEVIER_API_KEY")
    if not api_key:
        raise RuntimeError("ScienceDirect API key not configured")

    base_url = (
        provider.get("base_url")
        if provider and provider.get("base_url")
        else "https://api.elsevier.com/content/search/sciencedirect"
    )

    return api_key, base_url


def search_sciencedirect(query: str, count: int = 5) -> str:
    api_key, base_url = _get_sciencedirect_config()

    headers = {
        "X-ELS-APIKey": api_key,
        "Accept": "application/json",
    }

    params = {
        "query": query,
        "count": count,
        "sort": "-date",
    }

    r = requests.get(base_url, headers=headers, params=params, timeout=30)
    r.raise_for_status()
    return str(r.json())


def get_sciencedirect_article_by_pii(pii: str) -> str:
    api_key, _ = _get_sciencedirect_config()

    url = f"https://api.elsevier.com/content/article/pii/{pii}"

    headers = {
        "X-ELS-APIKey": api_key,
        "Accept": "application/json",
    }

    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return str(r.json())


def get_sciencedirect_article_by_doi(doi: str) -> str:
    api_key, _ = _get_sciencedirect_config()

    url = f"https://api.elsevier.com/content/article/doi/{doi}"

    headers = {
        "X-ELS-APIKey": api_key,
        "Accept": "application/json",
    }

    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return str(r.json())
