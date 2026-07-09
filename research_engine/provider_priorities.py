FIELD_RULES = {

    "doi": {
        "providers": [
            "crossref",
            "scopus",
            "openalex",
            "ieee",
            "sciencedirect",
            "acm",
            "springer",
        ],
        "merge": "first_non_empty",
        "refresh_days": 365,
        "required": True,
        "indexed": False,
    },

    "title": {
        "providers": [
            "crossref",
            "scopus",
            "ieee",
            "openalex",
            "sciencedirect",
            "acm",
            "springer",
        ],
        "merge": "longest",
        "refresh_days": 365,
        "required": True,
        "indexed": True,
    },

    "authors": {
        "providers": [
            "crossref",
            "scopus",
            "openalex",
            "ieee",
            "acm",
            "springer",
        ],
        "merge": "union",
        "refresh_days": 365,
        "required": True,
        "indexed": True,
    },

    "abstract": {
        "providers": [
            "scopus",
            "sciencedirect",
            "ieee",
            "acm",
            "springer",
            "openalex",
        ],
        "merge": "longest",
        "refresh_days": 365,
        "required": True,
        "indexed": True,
    },

    "keywords": {
        "providers": [
            "scopus",
            "sciencedirect",
            "ieee",
            "acm",
            "springer",
            "openalex",
        ],
        "merge": "union",
        "refresh_days": 365,
        "required": False,
        "indexed": True,
    },

    "journal": {
        "providers": [
            "crossref",
            "scopus",
            "ieee",
            "springer",
        ],
        "merge": "first_non_empty",
        "refresh_days": 365,
        "required": True,
        "indexed": False,
    },

    "publisher": {
        "providers": [
            "crossref",
            "springer",
            "ieee",
            "acm",
            "sciencedirect",
        ],
        "merge": "first_non_empty",
        "refresh_days": 365,
        "required": False,
        "indexed": False,
    },

    "citations": {
        "providers": [
            "scopus",
            "semantic_scholar",
            "openalex",
        ],
        "merge": "maximum",
        "refresh_days": 30,
        "required": False,
        "indexed": False,
    },

    "references": {
        "providers": [
            "semantic_scholar",
            "scopus",
            "crossref",
        ],
        "merge": "union",
        "refresh_days": 30,
        "required": False,
        "indexed": False,
    },

    "affiliations": {
        "providers": [
            "scopus",
        ],
        "merge": "union",
        "refresh_days": 365,
        "required": False,
        "indexed": True,
    },

    "concepts": {
        "providers": [
            "openalex",
        ],
        "merge": "union",
        "refresh_days": 365,
        "required": False,
        "indexed": True,
    },

    "full_text": {
        "providers": [
            "sciencedirect",
            "ieee",
            "acm",
            "springer",
        ],
        "merge": "longest",
        "refresh_days": 365,
        "required": False,
        "indexed": True,
    },

    "pdf_url": {
        "providers": [
            "openalex",
            "sciencedirect",
            "ieee",
            "acm",
            "springer",
        ],
        "merge": "first_non_empty",
        "refresh_days": 365,
        "required": False,
        "indexed": False,
    },
}


def rule(field):
    return FIELD_RULES.get(field, {})


def providers_for_field(field):
    return rule(field).get("providers", [])


def merge_strategy(field):
    return rule(field).get("merge")


def refresh_days(field):
    return rule(field).get("refresh_days", 365)


def required_fields():
    return [
        f
        for f, r in FIELD_RULES.items()
        if r.get("required")
    ]
