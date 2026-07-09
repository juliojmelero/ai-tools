import os
import requests
import arxiv
from fastapi import FastAPI, Query
from tavily import TavilyClient

app = FastAPI(title="AI Tools API")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/search/web")
def search_web(q: str = Query(...), max_results: int = 5):
    client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    return client.search(query=q, max_results=max_results)


@app.get("/search/arxiv")
def search_arxiv(q: str = Query(...), max_results: int = 5):
    search = arxiv.Search(
        query=q,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
    )

    results = []
    client = arxiv.Client()

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

    return {"query": q, "results": results}


@app.get("/search/scopus")
def search_scopus(q: str = Query(...), count: int = 10):
    api_key = os.environ["SCOPUS_API_KEY"]

    url = "https://api.elsevier.com/content/search/scopus"
    headers = {
        "X-ELS-APIKey": api_key,
        "Accept": "application/json",
    }
    params = {
        "query": q,
        "count": count,
        "sort": "-coverDate",
    }

    inst_token = os.getenv("SCOPUS_INST_TOKEN")
    if inst_token:
        headers["X-ELS-Insttoken"] = inst_token

    r = requests.get(url, headers=headers, params=params, timeout=30)
    r.raise_for_status()
    return r.json()
