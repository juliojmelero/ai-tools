from dataclasses import dataclass, asdict
from datetime import datetime
import math
from numbers import Real
from typing import Any, Optional


class InvalidProviderValueQualityError(ValueError):
    """Raised when a provider observation has an invalid quality score."""


@dataclass(frozen=True, slots=True)
class ProviderValue:
    provider: str
    value: Any
    timestamp: str
    quality: Optional[float] = None
    current: bool = False

    def __post_init__(self):
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
            timestamp=timestamp or datetime.utcnow().isoformat() + "Z",
        )

    def to_dict(self):
        self.validate_quality()
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(**data)
