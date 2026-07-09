import os
import requests


BASE_URL = "https://api.semanticscholar.org/graph/v1"


FIELDS = ",".join([
    "paperId",
    "title",
    "abstract",
    "year",
    "authors",
    "venue",
    "publicationVenue",
    "publicationTypes",
    "citationCount",
    "referenceCount",
    "influentialCitationCount",
    "isOpenAccess",
    "openAccessPdf",
    "url",
    "externalIds",
    "tldr",
])


def _headers():
    api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
    return {"x-api-key": api_key} if api_key else {}


def _get(url, params=None):
    r = requests.get(url, params=params or {}, headers=_headers(), timeout=30)
    if not r.ok:
        return {
            "status": "error",
            "status_code": r.status_code,
            "url": r.url,
            "response": r.text[:1000],
        }
    return r.json()


def _paper_summary(item):
    external_ids = item.get("externalIds") or {}
    open_pdf = item.get("openAccessPdf") or {}
    tldr = item.get("tldr") or {}

    return {
        "paper_id": item.get("paperId"),
        "title": item.get("title"),
        "abstract": item.get("abstract"),
        "year": item.get("year"),
        "venue": item.get("venue"),
        "publication_types": item.get("publicationTypes"),
        "authors": [
            {
                "name": a.get("name"),
                "author_id": a.get("authorId"),
            }
            for a in item.get("authors", [])
        ],
        "doi": external_ids.get("DOI"),
        "arxiv": external_ids.get("ArXiv"),
        "citation_count": item.get("citationCount"),
        "influential_citation_count": item.get("influentialCitationCount"),
        "reference_count": item.get("referenceCount"),
        "is_open_access": item.get("isOpenAccess"),
        "open_access_pdf": open_pdf.get("url"),
        "url": item.get("url"),
        "tldr": tldr.get("text"),
    }


def search_semantic_scholar(query: str, limit: int = 5, year: str | None = None) -> str:
    params = {
        "query": query,
        "limit": min(limit, 20),
        "fields": FIELDS,
    }

    if year:
        params["year"] = year

    data = _get(f"{BASE_URL}/paper/search", params)

    if data.get("status") == "error":
        return str(data)

    return str({
        "query": query,
        "returned_records": len(data.get("data", [])),
        "results": [_paper_summary(p) for p in data.get("data", [])],
    })


def get_paper(paper_id: str) -> str:
    """
    paper_id puede ser PaperId, DOI, DOI:..., ARXIV:..., CorpusId:...
    """
    if paper_id.startswith("10."):
        paper_id = "DOI:" + paper_id

    data = _get(
        f"{BASE_URL}/paper/{paper_id}",
        {"fields": FIELDS + ",citations.paperId,citations.title,citations.year,references.paperId,references.title,references.year"},
    )

    if data.get("status") == "error":
        return str(data)

    return str(data)


def get_author(author_id: str) -> str:
    fields = ",".join([
        "authorId",
        "name",
        "url",
        "homepage",
        "paperCount",
        "citationCount",
        "hIndex",
        "affiliations",
    ])

    data = _get(
        f"{BASE_URL}/author/{author_id}",
        {"fields": fields},
    )

    return str(data)


def get_author_papers(author_id: str, limit: int = 20) -> str:
    fields = ",".join([
        "papers.paperId",
        "papers.title",
        "papers.year",
        "papers.venue",
        "papers.citationCount",
        "papers.externalIds",
    ])

    data = _get(
        f"{BASE_URL}/author/{author_id}",
        {"fields": fields},
    )

    if data.get("status") == "error":
        return str(data)

    papers = data.get("papers", [])[:limit]

    return str({
        "author_id": author_id,
        "returned_records": len(papers),
        "papers": papers,
    })


def get_related_papers(paper_id: str, limit: int = 10) -> str:
    """
    Usa recomendaciones de Semantic Scholar a partir de un paper.
    """
    if paper_id.startswith("10."):
        paper_id = "DOI:" + paper_id

    url = f"{BASE_URL}/recommendations/v1/papers/forpaper/{paper_id}"

    data = _get(
        url,
        {
            "limit": min(limit, 100),
            "fields": FIELDS,
        },
    )

    if data.get("status") == "error":
        return str(data)

    papers = data.get("recommendedPapers", [])

    return str({
        "paper_id": paper_id,
        "returned_records": len(papers),
        "results": [_paper_summary(p) for p in papers],
    })


def get_most_cited(query: str, limit: int = 10, year: str | None = None) -> str:
    """
    Busca artículos y los ordena por número de citas.
    """
    raw = search_semantic_scholar(query=query, limit=min(limit, 20), year=year)
    data = eval(raw)

    if data.get("status") == "error":
        return str(data)

    results = data.get("results", [])
    results = sorted(
        results,
        key=lambda x: x.get("citation_count") or 0,
        reverse=True,
    )

    return str({
        "query": query,
        "returned_records": len(results[:limit]),
        "results": results[:limit],
    })


def find_review_papers(query: str, limit: int = 10, year: str | None = None) -> str:
    """
    Busca revisiones, surveys, tutorials y state-of-the-art papers.
    """
    review_query = f'({query}) review survey "state of the art" tutorial'

    raw = search_semantic_scholar(
        query=review_query,
        limit=min(limit, 20),
        year=year,
    )

    data = eval(raw)

    if data.get("status") == "error":
        return str(data)

    results = []

    for paper in data.get("results", []):
        title = (paper.get("title") or "").lower()
        abstract = (paper.get("abstract") or "").lower()
        types = paper.get("publication_types") or []

        text = title + " " + abstract

        is_review = (
            "review" in text
            or "survey" in text
            or "state of the art" in text
            or "tutorial" in text
            or any("Review" in str(t) for t in types)
        )

        if is_review:
            results.append(paper)

    return str({
        "query": query,
        "returned_records": len(results[:limit]),
        "results": results[:limit],
    })
