from research_config.providers import list_providers


def list_research_providers() -> str:
    """
    Lista los proveedores científicos configurados.
    No muestra API keys.
    """

    providers = []

    for p in list_providers():
        providers.append({
            "id": p.get("id"),
            "name": p.get("name"),
            "type": p.get("type"),
            "base_url": p.get("base_url"),
            "enabled": bool(p.get("enabled")),
            "has_api_key": bool(p.get("api_key")),
            "updated_at": p.get("updated_at"),
        })

    return str({
        "providers": providers,
        "count": len(providers),
    })
