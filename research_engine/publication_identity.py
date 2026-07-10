import hashlib
import json
import unicodedata
from dataclasses import dataclass
from typing import Any


_DOI_PREFIXES = (
    "https://dx.doi.org/",
    "http://dx.doi.org/",
    "https://doi.org/",
    "http://doi.org/",
    "doi:",
)

_TYPOGRAPHIC_PUNCTUATION = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201a": "'",
        "\u201b": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u201e": '"',
        "\u201f": '"',
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2015": "-",
        "\u2026": "...",
    }
)

_DECORATIVE_SURROUNDING_PUNCTUATION = frozenset(
    "'\".,:;!?-()[]{}<>"
)


@dataclass(frozen=True)
class PublicationIdentity:
    doi: str | None
    title: str | None


class PublicationIdentityResolver:
    """Normalize publication identifiers and produce stable cluster identities."""

    @staticmethod
    def normalize_doi(value: Any) -> str | None:
        if not isinstance(value, str):
            return None

        normalized = value.strip().lower()
        for prefix in _DOI_PREFIXES:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):].strip()
                break
        return normalized or None

    @staticmethod
    def normalize_title(value: Any) -> str | None:
        if not isinstance(value, str):
            return None

        normalized = unicodedata.normalize("NFC", value)
        normalized = PublicationIdentityResolver._normalize_punctuation_minus(
            normalized
        )
        normalized = normalized.translate(_TYPOGRAPHIC_PUNCTUATION).lower()
        normalized = " ".join(normalized.split())
        normalized = normalized.strip()
        normalized = PublicationIdentityResolver._strip_surrounding_punctuation(
            normalized
        )
        normalized = " ".join(normalized.split())
        return normalized or None

    def resolve(self, publication: Any) -> PublicationIdentity:
        return PublicationIdentity(
            doi=self.normalize_doi(self._field(publication, "doi")),
            title=self.normalize_title(self._field(publication, "title")),
        )

    @staticmethod
    def fallback_identity(publication: Any, occurrence: int = 0) -> str:
        serialized = PublicationIdentityResolver.record_sort_key(publication)
        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        return f"record:{digest}:{occurrence}"

    @staticmethod
    def record_sort_key(publication: Any) -> str:
        if isinstance(publication, dict):
            value = publication
        elif hasattr(publication, "__dict__"):
            value = vars(publication)
        else:
            value = str(publication)
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        )

    @staticmethod
    def _field(publication: Any, name: str) -> Any:
        if isinstance(publication, dict):
            return publication.get(name)
        return getattr(publication, name, None)

    @staticmethod
    def _strip_surrounding_punctuation(value: str) -> str:
        start = 0
        end = len(value)
        while (
            start < end
            and value[start] in _DECORATIVE_SURROUNDING_PUNCTUATION
        ):
            start += 1
        while (
            end > start
            and value[end - 1] in _DECORATIVE_SURROUNDING_PUNCTUATION
        ):
            end -= 1
        return value[start:end].strip()

    @staticmethod
    def _normalize_punctuation_minus(value: str) -> str:
        characters = list(value)
        for index, character in enumerate(characters):
            if character != "\u2212" or index == 0 or index == len(value) - 1:
                continue
            if not (value[index - 1].isalpha() and value[index + 1].isalpha()):
                continue

            left = index - 1
            while left >= 0 and value[left].isalpha():
                left -= 1
            right = index + 1
            while right < len(value) and value[right].isalpha():
                right += 1
            if index - left > 2 or right - index > 2:
                characters[index] = "-"
        return "".join(characters)
