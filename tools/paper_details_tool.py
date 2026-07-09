from tools.crossref_tool import get_crossref_work_by_doi
from tools.openalex_tool import get_openalex_work
from tools.scopus_tool import search_scopus
from tools.sciencedirect_tool import get_sciencedirect_article_by_doi


def get_paper_details(doi: str) -> str:
    """
    Recupera metadatos ampliados de un artículo usando DOI.
    Consulta Crossref, OpenAlex y ScienceDirect.
    """

    result = {
        "doi": doi,
        "crossref": None,
        "openalex": None,
        "sciencedirect": None,
        "errors": {}
    }

    try:
        result["crossref"] = get_crossref_work_by_doi(doi)
    except Exception as e:
        result["errors"]["crossref"] = str(e)

    try:
        result["openalex"] = get_openalex_work(doi)
    except Exception as e:
        result["errors"]["openalex"] = str(e)

    try:
        result["sciencedirect"] = get_sciencedirect_article_by_doi(doi)
    except Exception as e:
        result["errors"]["sciencedirect"] = str(e)

    return str(result)
