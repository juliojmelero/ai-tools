import inspect
import importlib
import pkgutil

from research_engine.base_provider import BaseProvider
import research_engine.providers as providers_pkg


class ProviderRegistry:

    def __init__(self):
        self._providers = {}
        self._discover()

    def _discover(self):

        for _, module_name, _ in pkgutil.iter_modules(providers_pkg.__path__):

            module = importlib.import_module(
                f"research_engine.providers.{module_name}"
            )

            for _, obj in inspect.getmembers(module, inspect.isclass):

                if obj is BaseProvider:
                    continue

                if not issubclass(obj, BaseProvider):
                    continue

                instance = obj()

                self._providers[instance.id] = instance

    def get(self, provider_id):

        return self._providers[provider_id]

    def get_optional(self, provider_id):

        return self._providers.get(provider_id)

    def contains(self, provider_id):

        return provider_id in self._providers

    def list(self):

        return list(self._providers.values())


_registry = ProviderRegistry()


def get_provider(provider_id):
    return _registry.get(provider_id)


def get_provider_optional(provider_id):
    return _registry.get_optional(provider_id)


def get_registry():
    return _registry


def list_providers():
    return _registry.list()
