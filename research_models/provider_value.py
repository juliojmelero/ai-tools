from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Optional


@dataclass
class ProviderValue:
    provider: str
    value: Any
    timestamp: str
    quality: Optional[float] = None

    @classmethod
    def create(
        cls,
        provider: str,
        value: Any,
        quality: Optional[float] = None,
    ):
        return cls(
            provider=provider,
            value=value,
            quality=quality,
            timestamp=datetime.utcnow().isoformat() + "Z",
        )

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(**data)
