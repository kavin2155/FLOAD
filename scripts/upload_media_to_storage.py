#!/usr/bin/env python3
import argparse
import mimetypes
import os
import re
import unicodedata
import zipfile
from contextlib import contextmanager
from pathlib import Path
from tempfile import SpooledTemporaryFile
from urllib.parse import quote

import psycopg
import requests


DEFAULT_BUCKET = "flood-media"
ZIP_MEMBER_PATTERN = re.compile(r"^(.+?\.zip(?:\.part\d+)?)/(.*)$")


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"{name} is missing. Add it to .env.")
    if name == "SUPABASE_URL":
        return value.rstrip("/")
    return value


def normalize_path(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def storage_path_for(row: dict[str, object]) -> str:
    source = str(row["source_dataset"] or "unknown")
    media_id = row["id"]
    original = Path(str(row["file_path"]))
    suffix = original.suffix.lower() or ".bin"
    return f"{source}/{media_id}{suffix}"


def guess_content_type(path: str) -> str:
    content_type, _ = mimetypes.guess_type(path)
    return content_type or "application/octet-stream"


def find_zip_member(zf: zipfile.ZipFile, member: str) -> str | None:
    member_nfc = normalize_path(member)
    member_name = Path(member_nfc).name

    for name in zf.namelist():
        if normalize_path(name) == member_nfc:
            return name

    for name in zf.namelist():
        if Path(normalize_path(name)).name == member_name:
            return name

    return None


@contextmanager
def open_media(file_path: str):
    path = normalize_path(file_path)
    local_path = Path(path)
    if local_path.exists():
        with local_path.open("rb") as f:
            yield f, local_path.name
        return

    match = ZIP_MEMBER_PATTERN.match(path)
    if not match:
        raise FileNotFoundError(file_path)

    zip_path = Path(match.group(1))
    member = match.group(2)
    if not zip_path.exists():
        raise FileNotFoundError(str(zip_path))

    with zipfile.ZipFile(zip_path, "r") as zf:
        actual_member = find_zip_member(zf, member)
        if actual_member is None:
            raise FileNotFoundError(f"{member} inside {zip_path}")

        with zf.open(actual_member, "r") as source:
            spool = SpooledTemporaryFile(max_size=64 * 1024 * 1024)
            while True:
                chunk = source.read(1024 * 1024)
                if not chunk:
                    break
                spool.write(chunk)
            spool.seek(0)
            try:
                yield spool, Path(actual_member).name
            finally:
                spool.close()


def create_bucket_if_needed(supabase_url: str, service_key: str, bucket: str) -> None:
    url = f"{supabase_url}/storage/v1/bucket"
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }
    response = requests.post(
        url,
        headers=headers,
        json={"id": bucket, "name": bucket, "public": False},
        timeout=30,
    )
    if response.status_code in {200, 201, 409}:
        return
    if response.status_code == 400 and "already exists" in response.text.lower():
        return
    response.raise_for_status()


def upload_object(
    supabase_url: str,
    service_key: str,
    bucket: str,
    object_path: str,
    file_obj,
    content_type: str,
) -> str:
    encoded_path = quote(object_path, safe="/")
    url = f"{supabase_url}/storage/v1/object/{bucket}/{encoded_path}"
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": content_type,
        "x-upsert": "true",
    }
    response = requests.put(url, headers=headers, data=file_obj, timeout=300)
    response.raise_for_status()
    return url


def fetch_media_rows(conn, source_dataset: str | None, limit: int | None, only_missing: bool):
    filters = []
    params: list[object] = []

    if source_dataset:
        filters.append("source_dataset = %s")
        params.append(source_dataset)

    if only_missing:
        filters.append("storage_path IS NULL")

    where_clause = ""
    if filters:
        where_clause = "WHERE " + " AND ".join(filters)

    limit_clause = ""
    if limit is not None:
        limit_clause = "LIMIT %s"
        params.append(limit)

    query = f"""
        SELECT id, file_path, media_type, source_dataset
        FROM cctv_media
        {where_clause}
        ORDER BY id
        {limit_clause}
    """

    with conn.cursor() as cur:
        cur.execute(query, params)
        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def mark_uploaded(conn, media_id: int, bucket: str, storage_path: str, storage_url: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE cctv_media
            SET storage_bucket = %s,
                storage_path = %s,
                storage_url = %s,
                storage_uploaded_at = NOW()
            WHERE id = %s
            """,
            (bucket, storage_path, storage_url, media_id),
        )


def main() -> None:
    load_dotenv(Path(".env"))

    parser = argparse.ArgumentParser(description="Upload cctv_media files to Supabase Storage.")
    parser.add_argument("--bucket", default=os.environ.get("SUPABASE_STORAGE_BUCKET", DEFAULT_BUCKET))
    parser.add_argument("--source-dataset", help="Upload only one source_dataset.")
    parser.add_argument("--limit", type=int, help="Maximum number of media records to process.")
    parser.add_argument("--include-uploaded", action="store_true", help="Re-upload rows that already have storage_path.")
    parser.add_argument("--dry-run", action="store_true", help="Resolve files and print planned uploads without uploading.")
    args = parser.parse_args()

    database_url = require_env("DATABASE_URL")
    supabase_url = None if args.dry_run else require_env("SUPABASE_URL")
    service_key = None if args.dry_run else require_env("SUPABASE_SERVICE_ROLE_KEY")

    with psycopg.connect(database_url) as conn:
        rows = fetch_media_rows(conn, args.source_dataset, args.limit, not args.include_uploaded)
        print(f"Found {len(rows)} media rows to process.")

        if not args.dry_run:
            assert supabase_url is not None
            assert service_key is not None
            create_bucket_if_needed(supabase_url, service_key, args.bucket)

        uploaded = 0
        skipped = 0
        for row in rows:
            object_path = storage_path_for(row)
            try:
                with open_media(str(row["file_path"])) as (media_file, resolved_name):
                    content_type = guess_content_type(resolved_name)
                    if args.dry_run:
                        print(f"[DRY-RUN] media_id={row['id']} -> {args.bucket}/{object_path} ({content_type})")
                    else:
                        assert supabase_url is not None
                        assert service_key is not None
                        storage_url = upload_object(
                            supabase_url,
                            service_key,
                            args.bucket,
                            object_path,
                            media_file,
                            content_type,
                        )
                        mark_uploaded(conn, int(row["id"]), args.bucket, object_path, storage_url)
                        uploaded += 1
                        if uploaded % 50 == 0:
                            conn.commit()
                            print(f"Uploaded {uploaded} files...")
            except Exception as exc:
                skipped += 1
                print(f"[SKIP] media_id={row['id']} {exc}")

        if not args.dry_run:
            conn.commit()

    print(f"Uploaded: {uploaded}")
    print(f"Skipped: {skipped}")


if __name__ == "__main__":
    main()
