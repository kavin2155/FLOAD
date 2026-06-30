#!/usr/bin/env python3
import argparse
import json
import os
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen
from urllib.error import HTTPError, URLError
from zoneinfo import ZoneInfo

import psycopg


KMA_BASE_URL = "https://apihub.kma.go.kr/api/typ01/url"
MISSING_VALUES = {"", "-9", "-9.0", "-99", "-99.0", "-999", "-999.0"}
KST = ZoneInfo("Asia/Seoul")


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def build_url(endpoint: str, params: dict[str, str]) -> str:
    return f"{KMA_BASE_URL}/{endpoint}?{urlencode(params)}"


def fetch_text(url: str) -> str:
    try:
        with urlopen(url, timeout=30) as response:
            raw = response.read()
            charset = response.headers.get_content_charset()
            encodings = [charset] if charset else []
            encodings.extend(["utf-8", "euc-kr", "cp949"])
            for encoding in encodings:
                if not encoding:
                    continue
                try:
                    return raw.decode(encoding)
                except UnicodeDecodeError:
                    pass
            return raw.decode("utf-8", errors="replace")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace").strip()
        message = f"KMA API request failed: HTTP {exc.code} {exc.reason}"
        if exc.code == 401:
            message += "\nCheck that KMA_API_KEY in .env is the real API key, not the example value."
        if body:
            message += f"\nResponse body:\n{body[:1000]}"
        raise SystemExit(message) from exc
    except URLError as exc:
        raise SystemExit(f"KMA API request failed: {exc.reason}") from exc


def normalize_header_name(name: str) -> str:
    return name.strip().upper().replace("-", "_")


def make_unique_headers(names: list[str]) -> list[str]:
    counts = {}
    unique_names = []
    known_duplicates = {
        "RN": ["RN", "RN_DAY", "RN_JUN", "RN_INT"],
        "SD": ["SD_HR3", "SD_DAY", "SD_TOT"],
        "GST": ["GST_WD", "GST_WS", "GST_TM"],
        "CA": ["CA_TOT", "CA_MID"],
        "CT": ["CT_MIN", "CT_TOP", "CT_MID", "CT_LOW"],
        "TE": ["TE_5", "TE_10", "TE_20", "TE_30"],
        "ST": ["ST_GD", "ST_SEA"],
    }

    for name in names:
        count = counts.get(name, 0)
        counts[name] = count + 1
        replacements = known_duplicates.get(name)
        if replacements and count < len(replacements):
            unique_names.append(replacements[count])
        elif count == 0:
            unique_names.append(name)
        else:
            unique_names.append(f"{name}_{count + 1}")

    return unique_names


def parse_kma_rows(text: str) -> list[dict[str, str]]:
    header = None
    rows = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("#"):
            candidate = line.lstrip("#").strip()
            names = [normalize_header_name(part) for part in candidate.split()]
            if ("STN" in names or "STN_ID" in names) and any(
                name in names for name in ("TM", "YYMMDDHHMI", "YYYYMMDDHHMI")
            ):
                header = make_unique_headers(names)
            continue

        if header is None:
            continue

        values = line.split()
        if len(values) < len(header):
            values.extend([""] * (len(header) - len(values)))

        rows.append(dict(zip(header, values[: len(header)])))

    return rows


def first_value(row: dict[str, str], names: tuple[str, ...]) -> str | None:
    for name in names:
        value = row.get(name)
        if value is not None and value not in MISSING_VALUES:
            return value
    return None


def parse_observed_at(value: str) -> datetime:
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) == 12:
        return datetime.strptime(digits, "%Y%m%d%H%M").replace(tzinfo=KST)
    if len(digits) == 10:
        return datetime.strptime(digits, "%Y%m%d%H").replace(tzinfo=KST)
    if len(digits) == 8:
        return datetime.strptime(digits, "%Y%m%d").replace(tzinfo=KST)
    raise ValueError(f"Unsupported KMA time value: {value}")


def parse_decimal(value: str | None) -> Decimal | None:
    if value is None or value in MISSING_VALUES:
        return None
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        return None
    if parsed < 0:
        return None
    return parsed


def parse_rainfall_mm(row: dict[str, str]) -> Decimal | None:
    rainfall = parse_decimal(first_value(row, ("RN",)))
    if rainfall is not None:
        return rainfall

    if row.get("IR") == "3":
        return Decimal("0")

    return None


def upsert_rainfall_rows(database_url: str, rows: list[dict[str, str]], source_api: str) -> int:
    parsed_rows = []

    for row in rows:
        station_code = first_value(row, ("STN", "STN_ID"))
        time_value = first_value(row, ("TM", "YYMMDDHHMI", "YYYYMMDDHHMI"))
        rainfall = parse_rainfall_mm(row)

        if station_code is None or time_value is None or rainfall is None:
            continue

        parsed_rows.append(
            {
                "station_code": station_code,
                "station_name": f"KMA-{station_code}",
                "observed_at": parse_observed_at(time_value),
                "rainfall": rainfall,
                "raw_payload": json.dumps(row, ensure_ascii=False),
            }
        )

    if not parsed_rows:
        return 0

    with psycopg.connect(database_url, prepare_threshold=None) as conn:
        with conn.cursor() as cur:
            station_ids = {}
            station_names = {
                parsed["station_code"]: parsed["station_name"]
                for parsed in parsed_rows
            }
            for station_code, station_name in station_names.items():
                cur.execute(
                    """
                    INSERT INTO weather_stations (station_code, station_name, source)
                    VALUES (%s, %s, 'KMA')
                    ON CONFLICT (station_code)
                    DO UPDATE SET station_name = EXCLUDED.station_name
                    RETURNING id
                    """,
                    (station_code, station_name),
                )
                station_ids[station_code] = cur.fetchone()[0]

            rainfall_values = [
                (
                    station_ids[parsed["station_code"]],
                    parsed["observed_at"],
                    parsed["rainfall"],
                    source_api,
                    parsed["raw_payload"],
                )
                for parsed in parsed_rows
            ]

            cur.executemany(
                """
                INSERT INTO rainfall_observations (
                    station_id,
                    observed_at,
                    rainfall_mm,
                    source_api,
                    raw_payload
                )
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (station_id, observed_at, source_api)
                DO UPDATE SET
                    rainfall_mm = EXCLUDED.rainfall_mm,
                    raw_payload = EXCLUDED.raw_payload,
                    collected_at = NOW()
                    """,
                rainfall_values,
            )

        conn.commit()

    return len(rainfall_values)


def main() -> None:
    load_dotenv(Path(".env"))

    parser = argparse.ArgumentParser(description="Collect KMA hourly rainfall into PostgreSQL.")
    parser.add_argument("--mode", choices=("realtime", "period"), default="period")
    parser.add_argument("--station", default="0", help="KMA station code. Use 0 for all available stations.")
    parser.add_argument("--start", help="Start time for period mode, e.g. 202406010000")
    parser.add_argument("--end", help="End time for period mode, e.g. 202406012300")
    parser.add_argument("--time", help="Observation time for realtime mode, e.g. 202406011200")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and parse without inserting into DB.")
    args = parser.parse_args()

    api_key = os.environ.get("KMA_API_KEY")
    if not api_key:
        raise SystemExit("KMA_API_KEY is missing. Copy .env.example to .env and put your KMA API key there.")
    if api_key == "your_kma_api_key_here":
        raise SystemExit("KMA_API_KEY still has the example value. Put your real KMA API key in .env.")

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is missing. Add your Supabase connection string to .env.")

    if args.mode == "period":
        if not args.start or not args.end:
            raise SystemExit("period mode requires --start and --end.")
        endpoint = "kma_sfctm3.php"
        params = {
            "tm1": args.start,
            "tm2": args.end,
            "stn": args.station,
            "help": "0",
            "authKey": api_key,
        }
    else:
        endpoint = "kma_sfctm2.php"
        params = {
            "stn": args.station,
            "help": "0",
            "authKey": api_key,
        }
        if args.time:
            params["tm"] = args.time

    url = build_url(endpoint, params)
    text = fetch_text(url)
    rows = parse_kma_rows(text)

    print(f"Fetched {len(rows)} KMA rows from {endpoint}.")
    if args.dry_run:
        for row in rows[:5]:
            print(row)
        return

    count = upsert_rainfall_rows(database_url, rows, endpoint)
    print(f"Inserted or updated {count} rainfall rows.")


if __name__ == "__main__":
    main()
