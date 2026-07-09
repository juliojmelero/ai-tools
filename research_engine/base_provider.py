from abc import ABC
from abc import abstractmethod


class BaseProvider(ABC):
    """
    Interfaz común que deberán implementar todos los
    proveedores bibliográficos.
    """

    id = None
    name = None

    @abstractmethod
    def search(
        self,
        query: str,
        max_results: int = 10,
        from_year: int | None = None,
        until_year: int | None = None,
    ):
        """
        Devuelve una lista de Publication.
        """
        raise NotImplementedError

    def is_enabled(self, provider_manager):
        return provider_manager.enabled(self.id)

    def api_key(self, provider_manager):
        return provider_manager.api_key(self.id)
