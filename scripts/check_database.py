#!/usr/bin/env python3
import os
from pathlib import Path
from urllib.parse import urlparse

import psycopg


TABLES = [
    "regions",
    "weather_stations",
    "rainfall_observations",
    "flood_history",
    "cctv_sources",
    "cctv_media",
    "flood_labels",
    "collection_runs",
]


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def describe_database(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.hostname or "unknown"
    port = parsed.port or ""
    database = parsed.path.lstrip("/") or "unknown"
    if "supabase" in host:
        kind = "Supabase PostgreSQL"
    else:
        kind = "PostgreSQL"
    return f"{kind} ({host}:{port}/{database})"


def main() -> None:
    load_dotenv(Path(".env"))
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is missing. Add your Supabase connection string to .env.")

    print(f"Database target: {describe_database(database_url)}")

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database(), current_user")
            database, user = cur.fetchone()
            print(f"Connected as {user} to {database}")
            print()
            print("Table row counts:")
            for table in TABLES:
                cur.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM information_schema.tables
                        WHERE table_schema = 'public'
                          AND table_name = %s
                    )
                    """,
                    (table,),
                )
                exists = cur.fetchone()[0]
                if not exists:
                    print(f"- {table}: missing")
                    continue

                cur.execute(f"SELECT COUNT(*) FROM {table}")
                count = cur.fetchone()[0]
                print(f"- {table}: {count}")

            cur.execute(
                """
                SELECT COUNT(*)
                FROM cctv_media
                WHERE storage_path IS NOT NULL
                """
            )
            uploaded_count = cur.fetchone()[0]
            print()
            print(f"Media uploaded to Storage: {uploaded_count}")


if __name__ == "__main__":
    main()
