from research_config.providers import (
    list_providers,
    get_provider,
    get_api_key,
)


class ProviderManager:
    """
    Capa de acceso a la configuración de proveedores.
    El resto del sistema nunca accederá directamente a SQLite.
    """

    def list(self):
        return list_providers()

    def list_enabled(self):
        return [
            p
            for p in list_providers()
            if p["enabled"]
        ]

    def get(self, provider_id):
        return get_provider(provider_id)

    def exists(self, provider_id):
        return get_provider(provider_id) is not None

    def enabled(self, provider_id):
        provider = get_provider(provider_id)
        return bool(provider and provider["enabled"])

    def api_key(self, provider_id):
        return get_api_key(provider_id)
