from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any

from .providers import (
    list_providers,
    get_provider,
    upsert_provider,
    delete_provider,
)

router = APIRouter(prefix="/providers", tags=["providers"])


class ProviderIn(BaseModel):
    id: str
    name: str
    type: str
    base_url: str | None = None
    api_key: str | None = None
    extra_config: dict[str, Any] = {}
    enabled: bool = True


@router.get("")
def api_list_providers():
    return list_providers()


@router.get("/{provider_id}")
def api_get_provider(provider_id: str):
    provider = get_provider(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider


@router.post("")
def api_upsert_provider(provider: ProviderIn):
    return upsert_provider(provider.model_dump())


@router.put("/{provider_id}")
def api_update_provider(provider_id: str, provider: ProviderIn):
    data = provider.model_dump()
    data["id"] = provider_id
    return upsert_provider(data)


@router.delete("/{provider_id}")
def api_delete_provider(provider_id: str):
    return delete_provider(provider_id)
