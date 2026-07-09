#Prioridad: ScienceDirect, IEEE Xplore, OpenAlex, Semantic Scholar, Crossref.
import ast

from tools.sciencedirect_tool import get_sciencedirect_article_by_doi
from tools.openalex_tool import get_openalex_work
from tools.semantic_scholar_tool import get_paper
from tools.crossref_tool import get_crossref_work_by_doi
from tools.ieee_tool import search_ieee

def _safe_parse(text):
    try:
        return ast.literal_eval(text)
    except Exception:
        return None


def find_fulltext(doi: str) -> str:
    """
    Busca texto completo o PDF disponible para un artículo usando su DOI.
    Prioridad: ScienceDirect, OpenAlex, Semantic Scholar, Crossref.
    """

    result = {
        "doi": doi,
        "best_source": None,
        "fulltext_available": False,
        "pdf_url": None,
        "landing_page_url": None,
        "sources": {},
        "errors": {}
    }

    # ScienceDirect
    try:
        raw = get_sciencedirect_article_by_doi(doi)
        data = _safe_parse(raw)

        result["sources"]["sciencedirect"] = data

        if isinstance(data, dict) and data.get("full-text-retrieval-response"):
            result["best_source"] = "sciencedirect"
            result["fulltext_available"] = True
            return str(result)

    except Exception as e:
        result["errors"]["sciencedirect"] = str(e)

    # IEEE Xplore
    try:
        raw = search_ieee(
            query=f'"{doi}"',
            max_records=1
        )
        data = _safe_parse(raw)

        result["sources"]["ieee"] = data

        if isinstance(data, dict):
            results = data.get("results", [])

            if results:
                item = results[0]
                pdf = item.get("pdf_url")
                html = item.get("html_url")

                if pdf or html:
                    result["best_source"] = "ieee"
                    result["fulltext_available"] = True
                    result["pdf_url"] = pdf
                    result["landing_page_url"] = html
                    return str(result)

    except Exception as e:
        result["errors"]["ieee"] = str(e)

    # OpenAlex
    try:
        raw = get_openalex_work(doi)
        data = _safe_parse(raw)

        result["sources"]["openalex"] = data

        if isinstance(data, dict):
            pdf = data.get("open_access_pdf")
            landing = data.get("landing_page_url") or data.get("url")

            if pdf:
                result["best_source"] = "openalex"
                result["fulltext_available"] = True
                result["pdf_url"] = pdf
                result["landing_page_url"] = landing
                return str(result)

    except Exception as e:
        result["errors"]["openalex"] = str(e)

    # Semantic Scholar
    try:
        raw = get_paper(doi)
        data = _safe_parse(raw)

        result["sources"]["semantic_scholar"] = data

        if isinstance(data, dict):
            open_pdf = data.get("openAccessPdf") or {}
            pdf = open_pdf.get("url")

            if pdf:
                result["best_source"] = "semantic_scholar"
                result["fulltext_available"] = True
                result["pdf_url"] = pdf
                result["landing_page_url"] = data.get("url")
                return str(result)

    except Exception as e:
        result["errors"]["semantic_scholar"] = str(e)

    # Crossref
    try:
        raw = get_crossref_work_by_doi(doi)
        data = _safe_parse(raw)

        result["sources"]["crossref"] = data

        if isinstance(data, dict):
            result["landing_page_url"] = data.get("url")

    except Exception as e:
        result["errors"]["crossref"] = str(e)

    return str(result)
