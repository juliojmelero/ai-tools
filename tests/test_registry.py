from research_engine.provider_registry import list_providers

providers = sorted([p.id for p in list_providers()])

print(providers)
