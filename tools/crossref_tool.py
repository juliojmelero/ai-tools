import os
import json
import requests

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


def search_crossref(
    query: str,
    rows: int = 5,
    from_year: int | None = None,
    until_year: int | None = None,
) -> str:
    """
    Busca publicaciones en Crossref usando metadatos bibliográficos.
    Devuelve resultados normalizados.
    """

    base_url, mailto = _crossref_config()

    params = {
        "query.bibliographic": query,
        "rows": rows,
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

    data = r.json()
    items = data.get("message", {}).get("items", [])

    publications = [
        crossref_to_publication(item)
        for item in items
    ]

    return str(publications_response(
        provider="crossref",
        query=query,
        publications=publications,
    ))


def get_crossref_work_by_doi(doi: str) -> str:
    """
    Recupera metadatos de Crossref para un DOI concreto.
    """

    base_url, mailto = _crossref_config()

    params = {}
    if mailto:
        params["mailto"] = mailto

    r = requests.get(
        f"{base_url}/works/{doi}",
        params=params,
        timeout=30,
    )
    r.raise_for_status()

    item = r.json().get("message", {})
    publication = crossref_to_publication(item)

    return str(publications_response(
        provider="crossref",
        query=doi,
        publications=[publication],
    ))
