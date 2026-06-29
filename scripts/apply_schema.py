#!/usr/bin/env python3
import os
from pathlib import Path

import psycopg


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def main() -> None:
    load_dotenv(Path(".env"))
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is missing. Add your Supabase connection string to .env.")

    schema = Path("db/schema.sql").read_text(encoding="utf-8")

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(schema)
        conn.commit()

    print("Schema applied.")


if __name__ == "__main__":
    main()
