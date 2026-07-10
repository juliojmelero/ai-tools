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


def _quality_key(quality):
    """Sort numeric qualities before None, with higher scores first."""
    return (quality is None, 0.0 if quality is None else -quality)


def _rank_by_provider_and_quality(item, provider_order):
    priorities = {name: index for index, name in enumerate(provider_order)}
    return (
        priorities.get(item.provider, len(priorities)),
        _quality_key(item.quality),
        "" if item.provider is None else str(item.provider),
    )


def first_non_empty(values, provider_order):
    chosen = min(
        values,
        key=lambda item: _rank_by_provider_and_quality(item, provider_order),
    )
    return chosen.value, chosen.provider


def longest(values, provider_order):
    longest_length = max(len(item.value) for item in values)
    candidates = [item for item in values if len(item.value) == longest_length]
    chosen = min(
        candidates,
        key=lambda item: _rank_by_provider_and_quality(item, provider_order),
    )
    return chosen.value, chosen.provider


def maximum(values, provider_order):
    maximum_value = max(item.value for item in values)
    candidates = [item for item in values if item.value == maximum_value]
    chosen = min(
        candidates,
        key=lambda item: _rank_by_provider_and_quality(item, provider_order),
    )
    return chosen.value, chosen.provider


def union(values, provider_order):
    result = []
    for provider_value in _ordered_values(values, provider_order):
        for item in provider_value.value:
            if item not in result:
                result.append(item)
    return result, None


def overwrite(values, provider_order):
    chosen = min(
        values,
        key=lambda item: _rank_by_provider_and_quality(item, provider_order),
    )
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
