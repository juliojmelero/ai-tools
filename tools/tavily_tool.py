import os
from tavily import TavilyClient

from research_config.providers import get_api_key


def search_web(query: str, max_results: int = 5) -> str:
    """
    Busca información actual en internet usando Tavily.
    """

    api_key = get_api_key("tavily") or os.getenv("TAVILY_API_KEY")

    if not api_key:
        raise RuntimeError("Tavily API key not configured")

    client = TavilyClient(api_key=api_key)

    result = client.search(
        query=query,
        max_results=max_results,
    )

    return str(result)
