import json
import sqlite3
from pathlib import Path
from datetime import datetime

from research_engine.fusion_engine import FusionEngine


CACHE_DB = Path("/app/data/research_cache.db")


def get_conn():
    CACHE_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(CACHE_DB)
    conn.row_factory = sqlite3.Row
    return conn


class CacheManager:

    def __init__(self):
        self.fusion = FusionEngine()

    def init_db(self):
        with get_conn() as conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS publications(
                doi TEXT PRIMARY KEY,
                provider TEXT,
                title TEXT,
                authors TEXT,
                abstract TEXT,
                journal TEXT,
                year INTEGER,
                citations INTEGER,
                publication_json TEXT,
                updated_at TEXT
            )
            """)

            conn.execute("""
            CREATE TABLE IF NOT EXISTS query_cache(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT,
                providers TEXT,
                sort_mode TEXT,
                from_year INTEGER,
                until_year INTEGER,
                max_results INTEGER,
                result_dois TEXT,
                created_at TEXT
            )
            """)

            conn.commit()

    def save_publications(self, publications):
        with get_conn() as conn:
            for p in publications:
                doi = p.get("doi")
                if not doi:
                    continue

                old = self.get_publication(doi)
                merged = self.fusion.merge(old, p)

                conn.execute("""
                INSERT OR REPLACE INTO publications(
                    doi,
                    provider,
                    title,
                    authors,
                    abstract,
                    journal,
                    year,
                    citations,
                    publication_json,
                    updated_at
                )
                VALUES(?,?,?,?,?,?,?,?,?,?)
                """, (
                    doi,
                    merged.get("provider"),
                    merged.get("title"),
                    json.dumps(merged.get("authors", []), ensure_ascii=False),
                    merged.get("abstract"),
                    merged.get("journal"),
                    merged.get("year"),
                    merged.get("citations"),
                    json.dumps(merged, ensure_ascii=False),
                    datetime.utcnow().isoformat(),
                ))

            conn.commit()

    def get_publication(self, doi):
        with get_conn() as conn:
            row = conn.execute("""
            SELECT publication_json
            FROM publications
            WHERE doi=?
            """, (doi,)).fetchone()

        if row is None:
            return None

        return json.loads(row["publication_json"])
