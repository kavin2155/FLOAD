#!/usr/bin/env python3
import argparse
import csv
import os
from pathlib import Path
from urllib.parse import urlparse

import psycopg


DEFAULT_OUTPUT_PATH = "outputs/training_dataset.csv"


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
    database = parsed.path.lstrip("/") or "unknown"
    if "supabase" in host:
        return f"Supabase DB ({host}/{database})"
    return f"PostgreSQL ({host}/{database})"


def build_query(source_dataset: str | None, label: str | None, limit: int | None) -> tuple[str, list[object]]:
    filters = []
    params: list[object] = []

    if source_dataset:
        filters.append("cm.source_dataset = %s")
        params.append(source_dataset)

    if label:
        filters.append("fl.label = %s")
        params.append(label)

    where_clause = ""
    if filters:
        where_clause = "WHERE " + " AND ".join(filters)

    limit_clause = ""
    if limit is not None:
        limit_clause = "LIMIT %s"
        params.append(limit)

    query = f"""
        SELECT
            cm.id AS media_id,
            cm.file_path,
            fl.label,
            cm.captured_at,
            cm.media_type,
            cm.source_dataset,
            cs.cctv_code,
            cs.cctv_name,
            cm.width,
            cm.height,
            cm.duration_sec,
            fl.label_source,
            fl.note
        FROM cctv_media cm
        JOIN flood_labels fl
            ON fl.cctv_media_id = cm.id
        LEFT JOIN cctv_sources cs
            ON cs.id = cm.cctv_source_id
        {where_clause}
        ORDER BY cm.id
        {limit_clause}
    """

    return query, params


def main() -> None:
    load_dotenv(Path(".env"))

    parser = argparse.ArgumentParser(description="Export image/video labels for flood detection model training.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_PATH, help="CSV output path.")
    parser.add_argument("--source-dataset", help="Filter by cctv_media.source_dataset.")
    parser.add_argument("--label", choices=("normal", "pre_flood", "flooded", "unknown"), help="Filter by label.")
    parser.add_argument("--limit", type=int, help="Maximum number of rows to export.")
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is missing. Add your Supabase connection string to .env.")
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Database target: {describe_database(database_url)}")
    print(f"Export target: {output_path}")

    query, params = build_query(args.source_dataset, args.label, args.limit)

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
            headers = [desc[0] for desc in cur.description]

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)

    print(f"Exported {len(rows)} rows.")


if __name__ == "__main__":
    main()
