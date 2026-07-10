from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import math
from numbers import Real
from typing import Any, Optional


class InvalidProviderValueQualityError(ValueError):
    """Raised when a provider observation has an invalid quality score."""


class InvalidProviderIdentifierError(ValueError):
    """Raised when an observation has no usable provider identifier."""


class InvalidProviderValueTimestampError(ValueError):
    """Raised when an observation timestamp is not valid ISO 8601."""


def normalize_provider_identifier(provider: str) -> str:
    if not isinstance(provider, str) or not provider.strip():
        raise InvalidProviderIdentifierError(
            f"Provider identifier must be a non-blank string; got {provider!r}"
        )
    return provider.strip()


def normalize_timestamp(timestamp, *, generate_default=True):
    if timestamp is None or (isinstance(timestamp, str) and not timestamp.strip()):
        if not generate_default:
            return None
        parsed = datetime.now(timezone.utc)
    elif not isinstance(timestamp, str):
        raise InvalidProviderValueTimestampError(
            f"ProviderValue timestamp must be a valid ISO 8601 string; got {timestamp!r}"
        )
    else:
        candidate = timestamp.strip()
        if candidate.endswith(("Z", "z")):
            candidate = candidate[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError as exc:
            raise InvalidProviderValueTimestampError(
                "ProviderValue timestamp must be a valid ISO 8601 string; "
                f"got {timestamp!r}"
            ) from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class ProviderValue:
    provider: str
    value: Any
    timestamp: Optional[str] = None
    quality: Optional[float] = None
    current: bool = False

    def __post_init__(self):
        object.__setattr__(
            self, "provider", normalize_provider_identifier(self.provider)
        )
        object.__setattr__(self, "timestamp", normalize_timestamp(self.timestamp))
        self.validate_quality()

    def validate_quality(self):
        if self.quality is None:
            return
        if (
            isinstance(self.quality, bool)
            or not isinstance(self.quality, Real)
            or not math.isfinite(self.quality)
            or not 0.0 <= self.quality <= 1.0
        ):
            raise InvalidProviderValueQualityError(
                "ProviderValue quality must be None or a finite numeric value "
                f"between 0.0 and 1.0; got {self.quality!r}"
            )

    @classmethod
    def create(
        cls,
        provider: str,
        value: Any,
        quality: Optional[float] = None,
        timestamp: Optional[str] = None,
    ):
        return cls(
            provider=provider,
            value=value,
            quality=quality,
            timestamp=timestamp,
        )

    def to_dict(self):
        provider = normalize_provider_identifier(self.provider)
        timestamp = normalize_timestamp(self.timestamp)
        self.validate_quality()
        data = asdict(self)
        data["provider"] = provider
        data["timestamp"] = timestamp
        return data

    @classmethod
    def from_dict(cls, data):
        payload = dict(data)
        payload["provider"] = normalize_provider_identifier(
            payload.get("provider")
        )
        payload["timestamp"] = normalize_timestamp(payload.get("timestamp"))
        return cls(**payload)
