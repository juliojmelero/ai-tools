import os
import requests

from research_config.providers import get_api_key, get_provider


def search_ieee(
    query: str,
    max_records: int = 5,
    start_year: int | None = None,
    end_year: int | None = None,
    content_type: str | None = None,
) -> str:
    """
    Busca artículos en IEEE Xplore.

    content_type puede ser:
    Journals, Conferences, Standards, Books, Early Access
    """

    provider = get_provider("ieee")

    api_key = get_api_key("ieee") or os.getenv("IEEE_API_KEY")
    if not api_key:
        raise RuntimeError("IEEE API key not configured")

    url = (
        provider.get("base_url")
        if provider and provider.get("base_url")
        else "https://ieeexploreapi.ieee.org/api/v1/search/articles"
    )

    params = {
        "apikey": api_key,
        "querytext": query,
        "max_records": max_records,
        "start_record": 1,
        "sort_field": "publication_year",
        "sort_order": "desc",
        "format": "json",
    }

    if start_year is not None:
        params["start_year"] = start_year

    if end_year is not None:
        params["end_year"] = end_year

    if content_type:
        params["content_type"] = content_type

    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()

    data = r.json()
    articles = data.get("articles", [])

    results = []

    for item in articles:
        results.append({
            "title": item.get("title"),
            "authors": item.get("authors", {}).get("authors", []),
            "publication_title": item.get("publication_title"),
            "publication_year": item.get("publication_year"),
            "content_type": item.get("content_type"),
            "doi": item.get("doi"),
            "abstract": item.get("abstract"),
            "html_url": item.get("html_url"),
            "pdf_url": item.get("pdf_url"),
            "is_number": item.get("is_number"),
            "article_number": item.get("article_number"),
        })

    return str({
        "query": query,
        "total_records": data.get("total_records"),
        "returned_records": len(results),
        "results": results,
    })
