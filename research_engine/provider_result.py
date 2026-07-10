from typing import Any, NotRequired, TypedDict

from research_engine.provider_priorities import FIELD_RULES
from research_models.provider_value import (
    ProviderValue,
    normalize_provider_identifier,
    normalize_timestamp,
)


class ProviderMetadata(TypedDict):
    provider: str
    quality: NotRequired[float | None]
    timestamp: NotRequired[str | None]


class ProviderResult(ProviderMetadata, total=False):
    """Canonical flat record returned by a bibliographic provider."""

    doi: Any
    title: Any
    authors: Any
    abstract: Any
    keywords: Any
    journal: Any
    publisher: Any
    citations: Any
    references: Any
    affiliations: Any
    concepts: Any
    full_text: Any
    pdf_url: Any


def provider_result(
    provider: str,
    *,
    quality: float | None = None,
    timestamp: str | None = None,
    **fields: Any,
) -> ProviderResult:
    """Build a provider result, discarding fields outside the canonical schema."""
    result: ProviderResult = {
        "provider": normalize_provider_identifier(provider)
    }
    if quality is not None:
        ProviderValue(
            provider=result["provider"],
            value=None,
            quality=quality,
            timestamp=None,
        )
        result["quality"] = quality
    normalized_timestamp = normalize_timestamp(timestamp, generate_default=False)
    if normalized_timestamp is not None:
        result["timestamp"] = normalized_timestamp
    result.update({key: value for key, value in fields.items() if key in FIELD_RULES})
    return result


def extract_provider_metadata(record: dict) -> dict[str, Any]:
    """Extract only metadata understood by Publication.add()."""
    return {
        "provider": normalize_provider_identifier(record.get("provider")),
        "quality": record.get("quality"),
        "timestamp": record.get("timestamp"),
    }
