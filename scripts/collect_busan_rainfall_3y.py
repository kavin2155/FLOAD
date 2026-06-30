#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import time
from datetime import date, datetime, timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
COLLECTOR = PROJECT_ROOT / "scripts" / "collect_kma_rainfall.py"
PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"
BUSAN_STATION = "159"


def add_month(day: date) -> date:
    if day.month == 12:
        return date(day.year + 1, 1, 1)
    return date(day.year, day.month + 1, 1)


def month_chunks(start: date, end: date):
    current = start
    while current <= end:
        next_month = add_month(date(current.year, current.month, 1))
        chunk_end = min(end, next_month - timedelta(days=1))
        yield current, chunk_end
        current = chunk_end + timedelta(days=1)


def fmt_start(day: date) -> str:
    return datetime(day.year, day.month, day.day, 0, 0).strftime("%Y%m%d%H%M")


def fmt_end(day: date) -> str:
    return datetime(day.year, day.month, day.day, 23, 0).strftime("%Y%m%d%H%M")


def main() -> None:
    # Current project 기준일: 2026-06-30. 정확히 최근 3년 범위를 채운다.
    start = date(2023, 6, 30)
    end = date(2026, 6, 30)

    for chunk_start, chunk_end in month_chunks(start, end):
        start_text = fmt_start(chunk_start)
        end_text = fmt_end(chunk_end)
        print(f"\n=== Collecting Busan rainfall: {start_text} ~ {end_text} ===", flush=True)
        for attempt in range(1, 4):
            result = subprocess.run(
                [
                    str(PYTHON),
                    str(COLLECTOR),
                    "--mode",
                    "period",
                    "--station",
                    BUSAN_STATION,
                    "--start",
                    start_text,
                    "--end",
                    end_text,
                ],
                cwd=PROJECT_ROOT,
            )
            if result.returncode == 0:
                break
            if attempt == 3:
                raise SystemExit(result.returncode)
            print(f"Retrying {start_text} ~ {end_text} after API error ({attempt}/3)...", flush=True)
            time.sleep(5 * attempt)


if __name__ == "__main__":
    main()
