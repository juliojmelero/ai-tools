from research_engine.provider_result import ProviderResult, provider_result


def _first(value, default=""):
    if isinstance(value, list) and value:
        return value[0]
    return value or default


def crossref_to_publication(item: dict) -> ProviderResult:
    authors = []

    for a in item.get("author", []):
        given = a.get("given", "")
        family = a.get("family", "")
        name = " ".join(x for x in [given, family] if x).strip()
        if name:
            authors.append(name)

    return provider_result(
        "crossref",
        quality=item.get("quality"),
        timestamp=item.get("timestamp"),
        title=_first(item.get("title")),
        authors=authors,
        journal=_first(item.get("container-title")),
        doi=item.get("DOI"),
        citations=item.get("is-referenced-by-count", 0),
        publisher=item.get("publisher", ""),
    )


def openalex_to_publication(item: dict) -> ProviderResult:
    authors = []

    for a in item.get("authorships", []):
        author = a.get("author", {})
        name = author.get("display_name")
        if name:
            authors.append(name)

    primary_location = item.get("primary_location") or {}
    source = primary_location.get("source") or {}

    return provider_result(
        "openalex",
        quality=item.get("quality"),
        timestamp=item.get("timestamp"),
        title=item.get("display_name") or "",
        authors=authors,
        abstract="",
        journal=source.get("display_name") or "",
        doi=(item.get("doi") or "").replace("https://doi.org/", "") or None,
        pdf_url=primary_location.get("pdf_url"),
        citations=item.get("cited_by_count", 0),
        publisher=source.get("host_organization_name") or "",
        concepts=[
            c.get("display_name")
            for c in item.get("concepts", [])
            if c.get("display_name")
        ],
    )


def scopus_to_publication(item: dict) -> ProviderResult:
    title = item.get("dc:title") or ""
    doi = item.get("prism:doi")

    authors = []
    creator = item.get("dc:creator")
    if creator:
        authors.append(creator)

    return provider_result(
        "scopus",
        quality=item.get("quality"),
        timestamp=item.get("timestamp"),
        title=title,
        authors=authors,
        journal=item.get("prism:publicationName") or "",
        doi=doi,
        citations=int(item.get("citedby-count", 0) or 0),
        publisher="Elsevier",
    )
