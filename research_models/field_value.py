from datetime import datetime, timezone
from dataclasses import dataclass, field, replace
import json
from typing import Any, Optional

from research_models.provider_value import ProviderValue
from research_engine.merge_strategies import select


@dataclass
class FieldValue:
    selected: Any = None
    merge_strategy: str = "first_non_empty"
    values: list[ProviderValue] = field(default_factory=list)
    _selected_provider: Optional[str] = field(default=None, init=False, repr=False)

    def __post_init__(self):
        self._validate_values()

    def _validate_values(self):
        for observation in self.values:
            if not isinstance(observation, ProviderValue):
                raise TypeError(
                    "FieldValue values must contain only ProviderValue observations"
                )
            observation.validate_quality()

    def add(
        self,
        provider: str,
        value: Any,
        quality: Optional[float] = None,
        provider_order=(),
        timestamp: Optional[str] = None,
    ):
        if value in (None, "", [], {}):
            return

        pv = ProviderValue.create(
            provider=provider,
            value=value,
            quality=quality,
            timestamp=timestamp,
        )

        self.values.append(pv)
        self.reselect(provider_order)

    def reselect(self, provider_order=()):
        current_values = self.current_values()
        self.selected, self._selected_provider = select(
            self.merge_strategy,
            current_values,
            provider_order,
        )

    @staticmethod
    def _timestamp_key(timestamp):
        """Return a comparable UTC key with a deterministic invalid fallback."""
        try:
            parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return 1, parsed.astimezone(timezone.utc)
        except (AttributeError, TypeError, ValueError):
            return 0, str(timestamp)

    @classmethod
    def _observation_key(cls, observation):
        # Timestamp establishes recency. Raw timestamp text distinguishes
        # equivalent spellings, and canonical content breaks remaining ties.
        content = json.dumps(
            {
                "provider": observation.provider,
                "quality": observation.quality,
                "value": observation.value,
            },
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return (
            cls._timestamp_key(observation.timestamp),
            str(observation.timestamp),
            content,
        )

    def current_values(self):
        """Return exactly one current (latest) observation per provider."""
        self._validate_values()
        # Canonical ordering makes the duplicate rule independent of arrival:
        # within an exactly identical group, historical copies precede one
        # current representative. Since those copies have identical complete
        # observation data, their relative identity is intentionally immaterial.
        self.values.sort(key=self._observation_key)

        latest = {}
        for observation in self.values:
            latest[observation.provider] = observation

        current_ids = {id(observation) for observation in latest.values()}
        self.values = [
            replace(observation, current=id(observation) in current_ids)
            for observation in self.values
        ]
        return [observation for observation in self.values if observation.current]

    def contributors(self):
        return sorted({v.provider for v in self.values})

    def selected_provider(self):
        return self._selected_provider

    def to_dict(self):
        self._validate_values()
        self.current_values()
        return {
            "selected": self.selected,
            "merge_strategy": self.merge_strategy,
            "selected_provider": self.selected_provider(),
            "contributors": self.contributors(),
            "values": [v.to_dict() for v in self.values],
        }

    @classmethod
    def from_dict(cls, data):
        obj = cls(
            selected=data.get("selected"),
            merge_strategy=data.get("merge_strategy", "first_non_empty"),
        )
        obj.values = [
            ProviderValue.from_dict(v)
            for v in data.get("values", [])
        ]
        obj._validate_values()
        obj.current_values()
        return obj
