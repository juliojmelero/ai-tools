from research_engine.providers.openalex import OpenAlexProvider


_provider = OpenAlexProvider()


def search_openalex_works(
    query: str,
    per_page: int = 5,
    from_year: int | None = None,
    until_year: int | None = None,
    sort: str = "cited_by_count:desc",
):
    """
    Herramienta MCP.
    Devuelve texto para Open WebUI.
    """

    result = _provider.search(
        query=query,
        max_results=per_page,
        from_year=from_year,
        until_year=until_year,
    )

    return str(result)


def get_openalex_work(openalex_id_or_doi: str):
    """
    Temporalmente reutilizamos la implementación antigua.
    En el siguiente paso la moveremos también al provider.
    """
    raise NotImplementedError(
        "get_openalex_work se migrará en el siguiente paso."
    )


def search_openalex_authors(*args, **kwargs):
    raise NotImplementedError()


def get_openalex_author(*args, **kwargs):
    raise NotImplementedError()


def search_openalex_institutions(*args, **kwargs):
    raise NotImplementedError()
