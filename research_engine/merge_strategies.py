class FusionConfigurationError(ValueError):
    """Raised when the configured fusion rules cannot be applied."""


def _provider_key(provider, provider_order):
    priorities = {name: index for index, name in enumerate(provider_order)}
    return (
        priorities.get(provider, len(priorities)),
        "" if provider is None else str(provider),
    )


def _ordered_values(values, provider_order):
    # Python's sort is stable, so values from one provider retain their
    # original order. The provider name makes unconfigured providers
    # deterministic too.
    return sorted(
        values,
        key=lambda item: _provider_key(item.provider, provider_order),
    )


def first_non_empty(values, provider_order):
    chosen = _ordered_values(values, provider_order)[0]
    return chosen.value, chosen.provider


def longest(values, provider_order):
    ordered = _ordered_values(values, provider_order)
    chosen = max(ordered, key=lambda item: len(item.value))
    return chosen.value, chosen.provider


def maximum(values, provider_order):
    ordered = _ordered_values(values, provider_order)
    chosen = max(ordered, key=lambda item: item.value)
    return chosen.value, chosen.provider


def union(values, provider_order):
    result = []
    for provider_value in _ordered_values(values, provider_order):
        for item in provider_value.value:
            if item not in result:
                result.append(item)
    return result, None


def overwrite(values, provider_order):
    chosen = _ordered_values(values, provider_order)[0]
    return chosen.value, chosen.provider


STRATEGIES = {
    "first_non_empty": first_non_empty,
    "longest": longest,
    "maximum": maximum,
    "union": union,
    "overwrite": overwrite,
}


def select(strategy_name, values, provider_order):
    try:
        strategy = STRATEGIES[strategy_name]
    except KeyError as exc:
        raise FusionConfigurationError(
            f"Unknown fusion strategy: {strategy_name!r}"
        ) from exc

    if not values:
        return None, None
    return strategy(values, provider_order)
