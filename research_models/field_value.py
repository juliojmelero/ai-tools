from dataclasses import dataclass
from typing import Optional
from dataclasses import field
from typing import Any

from research_models.provider_value import ProviderValue
from research_engine.merge_strategies import select


@dataclass
class FieldValue:
    selected: Any = None
    merge_strategy: str = "first_non_empty"
    values: list[ProviderValue] = field(default_factory=list)
    _selected_provider: Optional[str] = field(default=None, init=False, repr=False)

    def add(
        self,
        provider: str,
        value: Any,
        quality: Optional[float] = None,
        provider_order=(),
    ):
        if value in (None, "", [], {}):
            return

        pv = ProviderValue.create(
            provider=provider,
            value=value,
            quality=quality,
        )

        self.values.append(pv)
        self.reselect(provider_order)

    def reselect(self, provider_order=()):
        self.selected, self._selected_provider = select(
            self.merge_strategy,
            self.values,
            provider_order,
        )

    def contributors(self):
        return sorted({v.provider for v in self.values})

    def selected_provider(self):
        return self._selected_provider

    def to_dict(self):
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
        return obj
