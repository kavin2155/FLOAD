#!/usr/bin/env python3
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import gspread
import psycopg


KST = ZoneInfo("Asia/Seoul")
DEFAULT_SHEET_ID = "1gx7EI8ngK-dSwvHW3d5Qm97ClD4If218TXkIbfXORlo"
DEFAULT_WORKSHEET_NAME = "실시간_강수량"
DEFAULT_STATION_CODE = "159"


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
    return value


def get_gspread_client() -> gspread.Client | None:
    credentials_path = (
        os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
        or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    )
    if not credentials_path:
        print("Google Sheets sync skipped: GOOGLE_SERVICE_ACCOUNT_JSON is not set.")
        return None

    path = Path(credentials_path).expanduser()
    if not path.exists():
        print(f"Google Sheets sync skipped: credentials file not found: {path}")
        return None

    return gspread.service_account(filename=str(path))


def fetch_latest_rainfall_rows(database_url: str, station_code: str, limit: int) -> list[list[str]]:
    query = """
        SELECT
            ro.observed_at AT TIME ZONE 'Asia/Seoul' AS observed_at_kst,
            ws.station_code,
            ws.station_name,
            ro.rainfall_mm,
            ro.source_api,
            ro.collected_at AT TIME ZONE 'Asia/Seoul' AS collected_at_kst
        FROM rainfall_observations ro
        JOIN weather_stations ws ON ws.id = ro.station_id
        WHERE ws.station_code = %s
          AND ro.source_api = 'kma_sfctm2.php'
        ORDER BY ro.observed_at DESC
        LIMIT %s
    """

    rows = []
    with psycopg.connect(database_url, prepare_threshold=None) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (station_code, limit))
            for (
                observed_at,
                station_code_value,
                station_name,
                rainfall_mm,
                source_api,
                collected_at,
            ) in cur.fetchall():
                rows.append(
                    [
                        observed_at.strftime("%Y-%m-%d %H:%M"),
                        station_code_value,
                        station_name,
                        float(rainfall_mm),
                        source_api,
                        collected_at.strftime("%Y-%m-%d %H:%M:%S"),
                    ]
                )

    return rows


def get_or_create_worksheet(spreadsheet: gspread.Spreadsheet, title: str) -> gspread.Worksheet:
    try:
        return spreadsheet.worksheet(title)
    except gspread.WorksheetNotFound:
        return spreadsheet.add_worksheet(title=title, rows=500, cols=10)


def sync_sheet(rows: list[list[str]]) -> None:
    client = get_gspread_client()
    if client is None:
        return

    spreadsheet_id = os.environ.get("GOOGLE_SHEET_ID", DEFAULT_SHEET_ID)
    worksheet_name = os.environ.get(
        "GOOGLE_REALTIME_RAINFALL_SHEET_NAME",
        DEFAULT_WORKSHEET_NAME,
    )
    spreadsheet = client.open_by_key(spreadsheet_id)
    worksheet = get_or_create_worksheet(spreadsheet, worksheet_name)

    generated_at = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    values = [
        ["마지막 동기화", generated_at],
        [],
        ["관측시각(KST)", "지점코드", "지점명", "강수량(mm)", "출처 API", "DB 저장시각(KST)"],
        *rows,
    ]

    worksheet.clear()
    worksheet.update(values, "A1")
    worksheet.freeze(rows=3)

    print(f"Synced {len(rows)} realtime rainfall rows to Google Sheet: {worksheet_name}")


def main() -> None:
    load_dotenv(Path(".env"))

    database_url = require_env("DATABASE_URL")
    station_code = os.environ.get("KMA_REALTIME_STATION", DEFAULT_STATION_CODE)
    limit = int(os.environ.get("GOOGLE_REALTIME_RAINFALL_LIMIT", "300"))

    rows = fetch_latest_rainfall_rows(database_url, station_code, limit)
    sync_sheet(rows)


if __name__ == "__main__":
    main()
