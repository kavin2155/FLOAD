#!/usr/bin/env python3
import argparse
import json
import os
import unicodedata
import zipfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg

KST = ZoneInfo("Asia/Seoul")
DEFAULT_DATABASE_URL = "postgresql://flood_user:flood_pass@localhost:5432/flood_ai"
DEFAULT_DATASET_DIR = "/Users/jeong-yunhwan/Downloads/07.지능형_관제_서비스_CCTV_영상_데이터"


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def parse_date(date_str: str) -> datetime:
    # '241018' -> 2024년 10월 18일
    try:
        if len(date_str) == 6:
            return datetime.strptime(date_str, "%y%m%d").replace(tzinfo=KST)
        elif len(date_str) == 8:
            return datetime.strptime(date_str, "%Y%m%d").replace(tzinfo=KST)
    except ValueError:
        pass
    return datetime.now(KST)


def determine_label(zip_name: str) -> str:
    normalized_name = unicodedata.normalize("NFC", zip_name)
    if "0단계" in normalized_name:
        return "normal"
    elif "1단계" in normalized_name or "2단계" in normalized_name:
        return "flooded"
    return "unknown"


def main() -> None:
    load_dotenv(Path(".env"))

    parser = argparse.ArgumentParser(description="Ingest AI Hub CCTV video metadata and labels.")
    parser.add_argument("--dataset-dir", default=None, help="Path to the dataset root folder.")
    parser.add_argument("--dry-run", action="store_true", help="Print parsing results without saving to DB.")
    args = parser.parse_args()

    dataset_dir_str = args.dataset_dir or os.environ.get("DATASET_DIR") or DEFAULT_DATASET_DIR
    dataset_dir = Path(dataset_dir_str)

    if not dataset_dir.exists():
        raise SystemExit(f"Dataset directory not found: {dataset_dir}\nPlease specify with --dataset-dir or check DATASET_DIR in .env.")

    database_url = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

    data_dir = dataset_dir / "3.개방데이터" / "1.데이터"
    if not data_dir.exists():
        candidates = list(dataset_dir.glob("*개방데이터*"))
        if candidates:
            data_dir = candidates[0] / "1.데이터"
            if not data_dir.exists():
                candidates_sub = list(candidates[0].glob("*데이터*"))
                if candidates_sub:
                    data_dir = candidates_sub[0]

    if not data_dir.exists():
        raise SystemExit(f"Data folder structure not matched inside: {dataset_dir}")

    print(f"Data base path: {data_dir}")
    splits = ["Training", "Validation"]
    zip_files = []

    for split in splits:
        split_dir = data_dir / split
        if not split_dir.exists():
            candidates = list(data_dir.glob(f"*{split}*"))
            if candidates:
                split_dir = candidates[0]
            else:
                continue

        label_dir = split_dir / "02.라벨링데이터"
        if not label_dir.exists():
            candidates = list(split_dir.glob("*라벨링데이터*"))
            if candidates:
                label_dir = candidates[0]
            else:
                continue

        for f in label_dir.glob("*.zip*"):
            zip_files.append((split, f))

    print(f"Found {len(zip_files)} label ZIP files to process.")

    total_records = 0
    dry_run_samples = []

    conn = None
    if not args.dry_run:
        conn = psycopg.connect(database_url)
        cur = conn.cursor()

    try:
        for split, zip_path in zip_files:
            zip_name = zip_path.name
            ts_zip_name = zip_name.replace("TL_", "TS_")
            
            print(f"Processing ZIP: {zip_name} ({split})")

            with zipfile.ZipFile(zip_path, "r") as zf:
                for file_info in zf.infolist():
                    if not file_info.filename.endswith(".json"):
                        continue
                    
                    with zf.open(file_info) as f:
                        try:
                            data = json.load(f)
                        except json.JSONDecodeError as e:
                            print(f"Warning: Failed to parse JSON {file_info.filename} inside {zip_name}: {e}")
                            continue

                        metadata = data.get("metadata", {})
                        annotations = data.get("annotations", {})

                        file_name = metadata.get("file_name")
                        cctv_distribution = metadata.get("cctv_distribution")
                        date_str = metadata.get("date")
                        width = metadata.get("width")
                        height = metadata.get("height")
                        
                        event_length = annotations.get("event_length")
                        event_caption = annotations.get("event_caption")

                        if not file_name or not cctv_distribution:
                            continue

                        captured_at = parse_date(str(date_str))
                        virtual_video_path = f"{dataset_dir_str}/3.개방데이터/1.데이터/{split}/01.원천데이터/{ts_zip_name}/{file_name}"
                        label = determine_label(zip_name)

                        total_records += 1

                        if args.dry_run:
                            if len(dry_run_samples) < 5:
                                dry_run_samples.append({
                                    "cctv_code": cctv_distribution,
                                    "file_name": file_name,
                                    "captured_at": captured_at.isoformat(),
                                    "virtual_video_path": virtual_video_path,
                                    "label": label,
                                    "caption": event_caption
                                })
                        else:
                            cur.execute(
                                """
                                INSERT INTO cctv_sources (cctv_code, cctv_name, source)
                                VALUES (%s, %s, '지능형_관제_서비스_CCTV_영상_데이터')
                                ON CONFLICT (cctv_code) DO NOTHING
                                """,
                                (cctv_distribution, f"CCTV-{cctv_distribution}"),
                            )

                            cur.execute(
                                "SELECT id FROM cctv_sources WHERE cctv_code = %s",
                                (cctv_distribution,)
                            )
                            cctv_source_id = cur.fetchone()[0]

                            cur.execute(
                                """
                                INSERT INTO cctv_media (
                                    cctv_source_id,
                                    captured_at,
                                    media_type,
                                    file_path,
                                    width,
                                    height,
                                    duration_sec,
                                    source_dataset,
                                    raw_metadata
                                )
                                VALUES (%s, %s, 'video', %s, %s, %s, %s, '지능형_관제_서비스_CCTV_영상_데이터', %s)
                                ON CONFLICT (file_path) DO UPDATE SET
                                    captured_at = EXCLUDED.captured_at,
                                    width = EXCLUDED.width,
                                    height = EXCLUDED.height,
                                    duration_sec = EXCLUDED.duration_sec,
                                    raw_metadata = EXCLUDED.raw_metadata
                                RETURNING id
                                """,
                                (
                                    cctv_source_id,
                                    captured_at,
                                    virtual_video_path,
                                    width,
                                    height,
                                    event_length,
                                    json.dumps(data, ensure_ascii=False)
                                )
                            )
                            media_id = cur.fetchone()[0]

                            cur.execute(
                                """
                                INSERT INTO flood_labels (
                                    cctv_media_id,
                                    label,
                                    confidence,
                                    labeled_by,
                                    label_source,
                                    note
                                )
                                VALUES (%s, %s, 1.0000, 'AI Hub', '지능형_관제_서비스_CCTV_영상_데이터', %s)
                                ON CONFLICT (cctv_media_id, label_source) DO UPDATE SET
                                    label = EXCLUDED.label,
                                    note = EXCLUDED.note
                                """,
                                (media_id, label, event_caption)
                            )

            if not args.dry_run:
                conn.commit()
                print(f"Successfully committed ZIP: {zip_name}")

    finally:
        if conn:
            cur.close()
            conn.close()

    print("\n--- Ingestion Report ---")
    print(f"Total files parsed: {total_records}")
    if args.dry_run:
        print("Dry-run mode: No database changes were made.")
        print("Sample parsed records:")
        print(json.dumps(dry_run_samples, indent=2, ensure_ascii=False))
    else:
        print(f"Successfully inserted/updated {total_records} records in DB.")


if __name__ == "__main__":
    main()
