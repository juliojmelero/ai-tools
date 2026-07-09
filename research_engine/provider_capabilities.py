PROVIDER_CAPABILITIES = {
    "openalex": {
        "search",
        "metadata",
        "doi",
        "citations",
        "concepts",
        "open_access",
        "pdf",
    },
    "crossref": {
        "search",
        "metadata",
        "doi",
        "publisher",
        "issn",
        "funders",
    },
    "scopus": {
        "search",
        "metadata",
        "doi",
        "citations",
        "keywords",
        "affiliations",
    },
    "sciencedirect": {
        "search",
        "metadata",
        "doi",
        "abstract",
        "keywords",
        "full_text",
        "pdf",
    },
    "ieee": {
        "search",
        "metadata",
        "doi",
        "abstract",
        "citations",
        "full_text",
        "pdf",
    },
    "semantic_scholar": {
        "search",
        "metadata",
        "doi",
        "citations",
        "references",
        "recommendations",
        "embeddings",
    },
    "acm": {
        "search",
        "metadata",
        "doi",
        "abstract",
        "keywords",
        "full_text",
        "pdf",
        "proceedings",
    },
    "springer": {
        "search",
        "metadata",
        "doi",
        "abstract",
        "keywords",
        "full_text",
        "pdf",
        "books",
        "chapters",
    },
}


def get_capabilities(provider_id):
    return PROVIDER_CAPABILITIES.get(provider_id, set())


def has_capability(provider_id, capability):
    return capability in get_capabilities(provider_id)


def providers_with_capability(capability):
    return [
        provider_id
        for provider_id, capabilities in PROVIDER_CAPABILITIES.items()
        if capability in capabilities
    ]
