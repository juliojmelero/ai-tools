import arxiv


def search_arxiv(query: str, max_results: int = 5) -> str:
    """Busca artículos recientes en arXiv."""
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
    )

    client = arxiv.Client()
    results = []

    for r in client.results(search):
        results.append({
            "title": r.title,
            "authors": [a.name for a in r.authors],
            "published": r.published.isoformat(),
            "summary": r.summary,
            "url": r.entry_id,
            "pdf_url": r.pdf_url,
            "categories": r.categories,
        })

    return str(results)
