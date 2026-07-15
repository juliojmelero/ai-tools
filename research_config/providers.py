import json

from research_engine.query_cache import _increment_configuration_version

from .db import get_conn


def list_providers():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM providers ORDER BY id").fetchall()
        return [dict(r) for r in rows]


def get_provider(provider_id: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM providers WHERE id = ?",
            (provider_id,)
        ).fetchone()
        return dict(row) if row else None


def get_api_key(provider_id: str):
    provider = get_provider(provider_id)
    if not provider or not provider.get("enabled"):
        return None
    return provider.get("api_key")


def upsert_provider(data: dict):
    extra_config = data.get("extra_config", {})
    if isinstance(extra_config, dict):
        extra_config = json.dumps(extra_config)

    with get_conn() as conn:
        conn.execute("""
        INSERT INTO providers
        (id, name, type, base_url, api_key, extra_config, enabled, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name,
            type = excluded.type,
            base_url = excluded.base_url,
            api_key = excluded.api_key,
            extra_config = excluded.extra_config,
            enabled = excluded.enabled,
            updated_at = CURRENT_TIMESTAMP
        """, (
            data["id"],
            data["name"],
            data["type"],
            data.get("base_url"),
            data.get("api_key"),
            extra_config,
            int(data.get("enabled", 1)),
        ))
        conn.commit()

    _increment_configuration_version()
    return get_provider(data["id"])


def delete_provider(provider_id: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM providers WHERE id = ?", (provider_id,))
        conn.commit()
    _increment_configuration_version()
    return {"deleted": provider_id}
