from mcp.server.fastmcp import FastMCP

from tools.tavily_tool import search_web
from tools.arxiv_tool import search_arxiv
from tools.scopus_tool import search_scopus
from tools.health_tool import health
from tools.ieee_tool import search_ieee
from tools.crossref_tool import search_crossref, get_crossref_work_by_doi
from tools.semantic_scholar_tool import (
    search_semantic_scholar,
    get_paper,
    get_author,
    get_author_papers,
    get_related_papers,
    get_most_cited,
    find_review_papers,
)
from tools.openalex_tool import (
    search_openalex_works,
    get_openalex_work,
    search_openalex_authors,
    get_openalex_author,
    search_openalex_institutions,
)
from tools.sciencedirect_tool import (
    search_sciencedirect,
    get_sciencedirect_article_by_pii,
    get_sciencedirect_article_by_doi,
)
from tools.research_search_tool import research_search
from tools.paper_details_tool import get_paper_details
from tools.fulltext_tool import find_fulltext
from research_config.db import init_db
from tools.providers_tool import list_research_providers

mcp = FastMCP(
    "Research MCP",
    host="0.0.0.0",
    port=8000,
)

init_db()

mcp.tool()(health)
mcp.tool()(search_web)
mcp.tool()(search_arxiv)
mcp.tool()(search_scopus)
mcp.tool()(search_ieee)
mcp.tool()(search_crossref)
mcp.tool()(get_crossref_work_by_doi)
mcp.tool()(search_semantic_scholar)
mcp.tool()(get_paper)
mcp.tool()(get_author)
mcp.tool()(get_author_papers)
mcp.tool()(get_related_papers)
mcp.tool()(get_most_cited)
mcp.tool()(find_review_papers)
mcp.tool()(search_openalex_works)
mcp.tool()(get_openalex_work)
mcp.tool()(search_openalex_authors)
mcp.tool()(get_openalex_author)
mcp.tool()(search_openalex_institutions)
mcp.tool()(search_sciencedirect)
mcp.tool()(get_sciencedirect_article_by_pii)
mcp.tool()(get_sciencedirect_article_by_doi)
mcp.tool()(research_search)
mcp.tool()(get_paper_details)
mcp.tool()(find_fulltext)
mcp.tool()(list_research_providers)

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
