from .publication import Publication


def _first(value, default=""):
    if isinstance(value, list) and value:
        return value[0]
    return value or default


def _year_from_crossref(item: dict):
    for key in ["published-print", "published-online", "published", "issued"]:
        parts = item.get(key, {}).get("date-parts")
        if parts and parts[0]:
            return parts[0][0]
    return None


def crossref_to_publication(item: dict) -> Publication:
    authors = []

    for a in item.get("author", []):
        given = a.get("given", "")
        family = a.get("family", "")
        name = " ".join(x for x in [given, family] if x).strip()
        if name:
            authors.append(name)

    return Publication(
        provider="crossref",
        title=_first(item.get("title")),
        authors=authors,
        journal=_first(item.get("container-title")),
        year=_year_from_crossref(item),
        doi=item.get("DOI"),
        url=item.get("URL"),
        citations=item.get("is-referenced-by-count", 0),
        document_type=item.get("type", ""),
        publisher=item.get("publisher", ""),
        language=item.get("language", ""),
        extra={
            "score": item.get("score"),
            "issn": item.get("ISSN", []),
            "isbn": item.get("ISBN", []),
        },
    )


def openalex_to_publication(item: dict) -> Publication:
    authors = []

    for a in item.get("authorships", []):
        author = a.get("author", {})
        name = author.get("display_name")
        if name:
            authors.append(name)

    primary_location = item.get("primary_location") or {}
    source = primary_location.get("source") or {}

    open_access = item.get("open_access") or {}

    return Publication(
        provider="openalex",
        title=item.get("display_name") or "",
        authors=authors,
        abstract="",
        journal=source.get("display_name") or "",
        year=item.get("publication_year"),
        doi=(item.get("doi") or "").replace("https://doi.org/", "") or None,
        url=item.get("id"),
        pdf_url=primary_location.get("pdf_url"),
        citations=item.get("cited_by_count", 0),
        document_type=item.get("type") or "",
        publisher=source.get("host_organization_name") or "",
        open_access=open_access.get("is_oa"),
        extra={
            "openalex_id": item.get("id"),
            "landing_page_url": primary_location.get("landing_page_url"),
            "concepts": [
                c.get("display_name")
                for c in item.get("concepts", [])
                if c.get("display_name")
            ],
        },
    )


def scopus_to_publication(item: dict) -> Publication:
    title = item.get("dc:title") or ""
    doi = item.get("prism:doi")
    year = None

    cover_date = item.get("prism:coverDate")
    if cover_date:
        try:
            year = int(cover_date[:4])
        except Exception:
            year = None

    authors = []
    creator = item.get("dc:creator")
    if creator:
        authors.append(creator)

    return Publication(
        provider="scopus",
        title=title,
        authors=authors,
        journal=item.get("prism:publicationName") or "",
        year=year,
        doi=doi,
        url=item.get("prism:url") or item.get("link", [{}])[0].get("@href"),
        citations=int(item.get("citedby-count", 0) or 0),
        document_type=item.get("subtypeDescription") or item.get("subtype") or "",
        publisher="Elsevier",
        extra={
            "eid": item.get("eid"),
            "scopus_id": item.get("dc:identifier"),
            "cover_date": cover_date,
            "aggregation_type": item.get("prism:aggregationType"),
        },
    )
