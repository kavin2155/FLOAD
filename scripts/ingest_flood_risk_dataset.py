#!/usr/bin/env python3
import argparse
import json
import os
import zipfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg

KST = ZoneInfo("Asia/Seoul")
DEFAULT_DATABASE_URL = "postgresql://flood_user:flood_pass@localhost:5432/flood_ai"
DEFAULT_DATASET_DIR = "/Users/jeong-yunhwan/Downloads/135.부산시_침수위험_복합_데이터"


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
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=KST)
    except ValueError:
        pass
    return datetime.now(KST)


def parse_sigungu_from_path(filepath: str) -> str:
    # 예: '침수위험 수치모델 이미지 데이터/수영강/동래구/030yr_060/Dongnae_030_1_00012.json'
    parts = filepath.split('/')
    for part in parts:
        part = part.strip()
        if part.endswith("구") or part.endswith("군"):
            return part
    return "알수없음"


def main() -> None:
    load_dotenv(Path(".env"))

    parser = argparse.ArgumentParser(description="Ingest AI Hub Busan Flood Risk simulation dataset.")
    parser.add_argument("--dataset-dir", default=None, help="Path to the dataset root folder.")
    parser.add_argument("--dry-run", action="store_true", help="Print parsing results without saving to DB.")
    args = parser.parse_args()

    dataset_dir_str = args.dataset_dir or os.environ.get("DATASET_DIR") or DEFAULT_DATASET_DIR
    dataset_dir = Path(dataset_dir_str)

    if not dataset_dir.exists():
        raise SystemExit(f"Dataset directory not found: {dataset_dir}\nPlease specify with --dataset-dir or check DATASET_DIR in .env.")

    database_url = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

    # 3.개방데이터/1.데이터
    data_dir = dataset_dir / "3.개방데이터" / "1.데이터"
    if not data_dir.exists():
        candidates = list(dataset_dir.glob("*개방데이터*"))
        if candidates:
            data_dir = candidates[0] / "1.데이터"

    if not data_dir.exists():
        raise SystemExit(f"Data folder structure not matched inside: {dataset_dir}")

    splits = [("Training", "TL.zip.part0"), ("Validation", "VL.zip.part0")]
    zip_files = []

    for split, zip_name in splits:
        zip_path = data_dir / split / "02.라벨링데이터" / zip_name
        if not zip_path.exists():
            # 대문자/소문자 또는 자소분리 대비 glob
            label_dir = data_dir / split / "02.라벨링데이터"
            if not label_dir.exists():
                candidates = list((data_dir / split).glob("*라벨링데이터*"))
                if candidates:
                    label_dir = candidates[0]
            
            if label_dir.exists():
                candidates_zip = list(label_dir.glob("*.zip*"))
                if candidates_zip:
                    zip_path = candidates_zip[0]

        if zip_path.exists():
            zip_files.append((split, zip_path))

    print(f"Found {len(zip_files)} label ZIP files to process.")

    conn = None
    if not args.dry_run:
        print("Connecting to database...")
        conn = psycopg.connect(database_url)
        cur = conn.cursor()

    cctv_source_cache = {}
    total_records = 0
    try:
        for split, zip_path in zip_files:
            zip_name = zip_path.name
            ts_zip_name = zip_name.replace("TL", "TS").replace("VL", "VS")
            print(f"Processing ZIP: {zip_name} ({split})")

            with zipfile.ZipFile(zip_path, "r") as zf:
                for file_info in zf.infolist():
                    if not file_info.filename.endswith(".json"):
                        continue
                    
                    with zf.open(file_info) as f:
                        try:
                            data = json.load(f)
                        except json.JSONDecodeError as e:
                            print(f"Warning: Failed to parse JSON {file_info.filename}: {e}")
                            continue

                        info = data.get("INFO", {})
                        categories = data.get("CATEGORIES", {})
                        image = data.get("IMAGE", {})

                        # 필수 메타데이터 파싱
                        scenario_name = categories.get("NAME")
                        file_name = image.get("FILE_NAME")
                        category_val = categories.get("CATEGORY")  # 1: flooded, 0: normal
                        
                        if not scenario_name or not file_name:
                            continue

                        data_created = info.get("DATA_CREATED", "2023-10-31")
                        captured_at = parse_date(str(data_created))
                        sigungu = parse_sigungu_from_path(file_info.filename)
                        
                        width = int(image.get("WIDTH", 2400))
                        height = int(image.get("HEIGHT", 1600))
                        
                        # 가상 파일 경로 매핑
                        virtual_file_path = f"{dataset_dir_str}/3.개방데이터/1.데이터/{split}/01.원천데이터/{ts_zip_name}/{file_name}.jpg"

                        # 침수 라벨 파싱
                        has_flood = True if category_val == 1 else False
                        flood_level = "flooded" if has_flood else "normal"
                        
                        hr_rainfall = info.get("1HR_RAINFALL", 0.0)
                        note = f"1HR_RAINFALL: {hr_rainfall}mm, sigungu: {sigungu}"

                        if args.dry_run:
                            if total_records < 5:
                                print(f"[DRY-RUN] Scenario: {scenario_name}, Sigungu: {sigungu}, File: {file_name}, Flood: {flood_level}, Note: {note}")
                            total_records += 1
                            continue

                        # 1. cctv_sources 테이블 인서트 (메모리 캐싱으로 쿼리 최적화)
                        if scenario_name in cctv_source_cache:
                            cctv_source_id = cctv_source_cache[scenario_name]
                        else:
                            # 1단계: cctv_sources에 삽입
                            cur.execute("""
                                INSERT INTO cctv_sources (cctv_code, cctv_name, source)
                                VALUES (%s, %s, '부산시_침수위험_복합_데이터')
                                ON CONFLICT (cctv_code) DO NOTHING
                            """, (scenario_name, f"SIM-{scenario_name}"))
                            
                            # ID 획득
                            cur.execute("SELECT id FROM cctv_sources WHERE cctv_code = %s", (scenario_name,))
                            cctv_source_id = cur.fetchone()[0]
                            cctv_source_cache[scenario_name] = cctv_source_id

                        # 2. cctv_media 테이블 인서트 (JSON 전체는 raw_metadata에 저장)
                        cur.execute("""
                            INSERT INTO cctv_media (
                                cctv_source_id, captured_at, media_type, file_path, width, height, duration_sec, source_dataset, raw_metadata
                            )
                            VALUES (%s, %s, 'image', %s, %s, %s, 0.0, '부산시_침수위험_복합_데이터', %s)
                            ON CONFLICT (file_path) DO UPDATE SET
                                captured_at = EXCLUDED.captured_at,
                                raw_metadata = EXCLUDED.raw_metadata
                            RETURNING id;
                        """, (cctv_source_id, captured_at, virtual_file_path, width, height, json.dumps(data, ensure_ascii=False)))
                        cctv_media_id = cur.fetchone()[0]

                        # 3. flood_labels 테이블 인서트 (침수 단계 및 어노테이션 정보 연동)
                        cur.execute("""
                            INSERT INTO flood_labels (cctv_media_id, label, confidence, labeled_by, label_source, note)
                            VALUES (%s, %s, 1.0000, 'AI Hub', '부산시_침수위험_복합_데이터', %s)
                            ON CONFLICT (cctv_media_id, label_source) DO UPDATE SET
                                label = EXCLUDED.label,
                                note = EXCLUDED.note;
                        """, (cctv_media_id, flood_level, note))

                        total_records += 1
                        if total_records % 500 == 0:
                            print(f"Ingested {total_records} records...")
                            conn.commit()

        if not args.dry_run and conn:
            conn.commit()
            print(f"\nSuccessfully Ingested total {total_records} records into remote Supabase DB!")
        else:
            print(f"\n[DRY-RUN] Total {total_records} records scanned.")

    finally:
        if conn:
            cur.close()
            conn.close()


if __name__ == "__main__":
    main()
