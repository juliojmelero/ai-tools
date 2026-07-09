import ast
import re
from difflib import SequenceMatcher

from tools.scopus_tool import search_scopus
from tools.crossref_tool import search_crossref
from tools.openalex_tool import search_openalex_works
from tools.arxiv_tool import search_arxiv
from tools.sciencedirect_tool import search_sciencedirect


def _safe_parse(text):
    try:
        return ast.literal_eval(text)
    except Exception:
        return None


def _normalize_doi(doi):
    if not doi:
        return None

    doi = str(doi).strip().lower()
    doi = doi.replace("https://doi.org/", "")
    doi = doi.replace("http://dx.doi.org/", "")
    doi = doi.replace("doi:", "")
    return doi.strip()


def _clean_title(title):
    if not title:
        return ""

    title = str(title).lower()
    title = re.sub(r"<[^>]+>", " ", title)
    title = re.sub(r"[^a-z0-9áéíóúüñ\s]", " ", title)
    title = re.sub(r"\s+", " ", title)
    return title.strip()

def _is_relevant(title, topic):
    title_clean = _clean_title(title)
    topic_clean = _clean_title(topic)

    if not title_clean or not topic_clean:
        return False

    topic_words = [
        w for w in topic_clean.split()
        if len(w) > 3
    ]

    if not topic_words:
        return False

    hits = sum(1 for w in topic_words if w in title_clean)

    return hits >= max(1, len(topic_words) // 2)

def _similar_title(a, b):
    if not a or not b:
        return False

    return SequenceMatcher(None, _clean_title(a), _clean_title(b)).ratio() > 0.92


def _add_record(records, record):
    doi = _normalize_doi(record.get("doi"))
    title = record.get("title")

    for existing in records:
        existing_doi = _normalize_doi(existing.get("doi"))

        if doi and existing_doi and doi == existing_doi:
            existing["sources"] = sorted(set(existing["sources"] + record["sources"]))
            existing.update({k: v for k, v in record.items() if v and not existing.get(k)})
            return

        if _similar_title(title, existing.get("title")):
            existing["sources"] = sorted(set(existing["sources"] + record["sources"]))
            existing.update({k: v for k, v in record.items() if v and not existing.get(k)})
            return

    records.append(record)


def _from_crossref(item):
    return {
        "title": item.get("title"),
        "doi": _normalize_doi(item.get("doi")),
        "year": item.get("year"),
        "authors": item.get("authors"),
        "source_title": item.get("journal_or_book"),
        "publisher": item.get("publisher"),
        "citation_count": item.get("citation_count_crossref"),
        "url": item.get("url"),
        "abstract": item.get("abstract"),
        "sources": ["crossref"],
    }


def _from_openalex(item):
    return {
        "title": item.get("title"),
        "doi": _normalize_doi(item.get("doi")),
        "year": item.get("publication_year"),
        "authors": item.get("authors"),
        "source_title": item.get("source"),
        "publisher": item.get("publisher"),
        "citation_count": item.get("cited_by_count"),
        "url": item.get("openalex_url"),
        "open_access_pdf": item.get("open_access_pdf"),
        "is_open_access": item.get("is_open_access"),
        "sources": ["openalex"],
    }


def _from_arxiv(item):
    return {
        "title": item.get("title"),
        "doi": None,
        "year": str(item.get("published", ""))[:4],
        "authors": item.get("authors"),
        "source_title": "arXiv",
        "url": item.get("url"),
        "open_access_pdf": item.get("pdf_url"),
        "abstract": item.get("summary"),
        "sources": ["arxiv"],
    }


def _from_sciencedirect(item):
    return {
        "title": item.get("dc:title") or item.get("title"),
        "doi": _normalize_doi(item.get("prism:doi") or item.get("doi")),
        "year": str(item.get("prism:coverDate", ""))[:4],
        "authors": item.get("authors"),
        "source_title": item.get("prism:publicationName"),
        "url": item.get("prism:url") or item.get("link"),
        "sources": ["sciencedirect"],
    }


def _from_scopus(item):
    return {
        "title": item.get("dc:title"),
        "doi": _normalize_doi(item.get("prism:doi")),
        "year": str(item.get("prism:coverDate", ""))[:4],
        "authors": item.get("dc:creator"),
        "source_title": item.get("prism:publicationName"),
        "citation_count": item.get("citedby-count"),
        "url": item.get("prism:url"),
        "eid": item.get("eid"),
        "sources": ["scopus"],
    }


def research_search(
    topic: str,
    from_year: int | None = None,
    max_results: int = 20,
) -> str:
    """
    Búsqueda bibliográfica unificada en Scopus, Crossref, OpenAlex, arXiv y ScienceDirect.
    Elimina duplicados por DOI y por similitud de título.
    """

    records = []
    errors = {}

    # Scopus
    try:
        query = f'TITLE-ABS-KEY("{topic}")'
        raw = search_scopus(query=f'TITLE-ABS-KEY("{topic}")',count=min(max_results * 2, 50))
        data = _safe_parse(raw)

        entries = []
        if isinstance(data, dict):
            entries = data.get("search-results", {}).get("entry", [])

        for item in entries:
            _add_record(records, _from_scopus(item))

    except Exception as e:
        errors["scopus"] = str(e)

    # Crossref
    try:
        raw = search_crossref(query=topic,rows=5,from_year=from_year)
        data = _safe_parse(raw)

        for item in (data or {}).get("results", []):
            _add_record(records, _from_crossref(item))

    except Exception as e:
        errors["crossref"] = str(e)

    # OpenAlex
    try:
        raw = search_openalex_works(
        query=topic,
        per_page=5,
        from_year=from_year,
        sort="relevance_score:desc",
        )
        data = _safe_parse(raw)

        for item in (data or {}).get("results", []):
            _add_record(records, _from_openalex(item))

    except Exception as e:
        errors["openalex"] = str(e)

    # arXiv
    try:
        raw = search_arxiv(query=topic, max_results=min(max_results, 10))
        data = _safe_parse(raw)

        for item in data or []:
            _add_record(records, _from_arxiv(item))

    except Exception as e:
        errors["arxiv"] = str(e)

    # ScienceDirect
    try:
        raw = search_sciencedirect(query=topic, count=min(max_results, 10))
        data = _safe_parse(raw)

        entries = []
        if isinstance(data, dict):
            entries = data.get("search-results", {}).get("entry", [])

        for item in entries:
            _add_record(records, _from_sciencedirect(item))

    except Exception as e:
        errors["sciencedirect"] = str(e)

    def source_score(p):
        sources = p.get("sources", [])
        score_value = 0

        if "scopus" in sources:
            score_value += 500
        if "sciencedirect" in sources:
            score_value += 500
        if "ieee" in sources:
            score_value += 500
        if "semantic_scholar" in sources:
            score_value += 200
        if "openalex" in sources:
            score_value += 120
        if "crossref" in sources:
            score_value += 80
        if "arxiv" in sources:
            score_value += 60

        return score_value


    def citation_score(p):
        try:
            return min(int(p.get("citation_count") or 0), 100)
        except Exception:
            return 0


    def recency_score(p):
        try:
            year = int(p.get("year") or 0)
            return max(0, year - 2020) * 5
        except Exception:
            return 0


    def relevance_score(p):
        return source_score(p) + citation_score(p) + recency_score(p)


    def score(p):
        return relevance_score(p)
        
    records = [
    p for p in records
    if _is_relevant(p.get("title"), topic)
    ]
    compact_records = []

    for i, p in enumerate(records[:max_results], start=1):
            compact_records.append({
                "rank": i,
                "title": p.get("title"),
                "doi": p.get("doi"),
                "year": p.get("year"),
                "source_title": p.get("source_title"),
                "citation_count": p.get("citation_count"),
                "sources": p.get("sources"),
                "matched_sources": len(p.get("sources", [])),
                "source_score": source_score(p),
                "citation_score": citation_score(p),
                "recency_score": recency_score(p),
                "relevance_score": relevance_score(p),
                "eid": p.get("eid"),
                "open_access_pdf": p.get("open_access_pdf"),
            })

    return str({
        "topic": topic,
        "from_year": from_year,
        "returned_records": len(compact_records),
        "errors": errors,
        "results": compact_records,
        "note": "Use get_paper_details with DOI or EID to retrieve full metadata."
    })
