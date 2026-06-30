#!/usr/bin/env python3
import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

KST = ZoneInfo("Asia/Seoul")
API_URL = "https://www.safetydata.go.kr/V2/api/DSSP-IF-00117"
BUSAN_SIGUNGU_BY_CODE = {
    "26110": "중구",
    "26140": "서구",
    "26170": "동구",
    "26200": "영도구",
    "26230": "부산진구",
    "26260": "동래구",
    "26290": "남구",
    "26320": "북구",
    "26350": "해운대구",
    "26380": "사하구",
    "26410": "금정구",
    "26440": "강서구",
    "26470": "연제구",
    "26500": "수영구",
    "26530": "사상구",
    "26710": "기장군",
}


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def parse_timestamp(date_str: str, time_str: str) -> datetime | None:
    if not date_str:
        return None
    try:
        # 시간 문자열 포맷 검증 (예: '1600' -> '16:00')
        t_str = time_str if time_str and len(time_str) == 4 else "0000"
        dt_str = f"{date_str}{t_str}"
        return datetime.strptime(dt_str, "%Y%m%d%H%M").replace(tzinfo=KST)
    except ValueError:
        try:
            return datetime.strptime(date_str, "%Y%m%d").replace(tzinfo=KST)
        except ValueError:
            return None


def main() -> None:
    load_dotenv(Path(".env"))

    parser = argparse.ArgumentParser(description="Collect Flood History from safetydata.go.kr")
    parser.add_argument("--busan-only", action="store_true", default=True, help="Collect only Busan region data (STDG_CTPV_CD=26)")
    parser.add_argument("--all-regions", action="store_false", dest="busan_only", help="Collect data for all regions")
    parser.add_argument("--limit-pages", type=int, default=0, help="Maximum number of pages to fetch. 0 for unlimited.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and parse without inserting into DB.")
    args = parser.parse_args()

    api_key = os.environ.get("SAFETY_DATA_API_KEY")
    if not api_key:
        raise SystemExit("SAFETY_DATA_API_KEY is missing. Add it to your .env file.")

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is missing. Add your Supabase connection string to .env.")

    page_no = 1
    num_of_rows = 100
    total_processed = 0

    print("Starting flood history collection...")
    print(f"Filter Busan Only: {args.busan_only}")

    conn = None
    if not args.dry_run:
        conn = psycopg.connect(database_url, prepare_threshold=None)
        cur = conn.cursor()

    try:
        while True:
            params = {
                "serviceKey": api_key,
                "returnType": "json",
                "pageNo": str(page_no),
                "numOfRows": str(num_of_rows),
            }

            print(f"Fetching page {page_no} (Rows: {num_of_rows})...")
            try:
                response = requests.get(API_URL, params=params, verify=False, timeout=30)
            except Exception as e:
                print(f"Request failed on page {page_no}: {e}")
                break

            if response.status_code != 200:
                print(f"Error: API returned HTTP {response.status_code}")
                break

            try:
                res_data = response.json()
            except json.JSONDecodeError:
                print("Failed to decode JSON response.")
                break

            body = res_data.get("body", [])
            total_count = res_data.get("totalCount", 0)

            if not body:
                print("No more records returned from API.")
                break

            # 필터링 및 적재 처리
            page_processed = 0
            for item in body:
                ctpv_cd = item.get("STDG_CTPV_CD")  # 시도 코드 (부산=26)
                
                # 부산 필터가 켜져있을 때 부산이 아니면 패스
                if args.busan_only and ctpv_cd != "26":
                    continue

                sn = item.get("SN")  # 고유 일련번호
                fldn_yr = item.get("FLDN_YR")  # 침수 연도
                fldn_dst_nm = item.get("FLDN_DST_NM")  # 침수 재해명
                fldn_cs_dtl_nm = item.get("FLDN_CS_DTL_NM")  # 침수 상세 원인
                fldn_area = item.get("FLDN_AREA")  # 침수 면적
                fldn_dowa = item.get("FLDN_DOWA")  # 침수 심도(m)
                geom_wkt = item.get("GEOM")  # 공간 WKT 데이터
                
                bgng_ymd = item.get("FLDN_BGNG_YMD")
                bgng_tm = item.get("FLDN_BGNG_TM")
                end_ymd = item.get("FLDN_END_YMD")
                end_tm = item.get("FLDN_END_TM")

                prv_nm = item.get("PRV_NM") or item.get("STDG_CTPV_NM") or "부산광역시"
                sgg_cd = item.get("STDG_SGG_CD")
                sgg_nm = item.get("SGG_NM") or item.get("STDG_SGG_NM")
                if ctpv_cd == "26" and sgg_cd:
                    sgg_nm = BUSAN_SIGUNGU_BY_CODE.get(sgg_cd, sgg_nm)

                # 시간 파싱
                started_at = parse_timestamp(str(bgng_ymd), str(bgng_tm))
                ended_at = parse_timestamp(str(end_ymd), str(end_tm))
                event_date = started_at.date() if started_at else None

                # 침수 깊이(cm 변환) 및 면적
                depth_cm = float(fldn_dowa) * 100.0 if fldn_dowa is not None else None
                area_sqm = float(fldn_area) if fldn_area is not None else None
                
                # 고유 식별자 조합 (소스로부터 고유키 지정)
                source_event_id = f"{sn}_{fldn_yr}" if sn and fldn_yr else str(sn)

                if args.dry_run:
                    if page_processed < 2:
                        print(f"[Dry-run Sample] Event ID: {source_event_id}, Date: {event_date}, Area: {area_sqm} sqm, Depth: {depth_cm} cm, Type: {fldn_dst_nm}")
                else:
                    # 1) regions 테이블에 매핑 시도 (sido, sigungu)
                    cur.execute(
                        """
                        INSERT INTO regions (sido, sigungu, eupmyeondong, legal_dong_code)
                        VALUES (%s, %s, NULL, %s)
                        ON CONFLICT (sido, sigungu, eupmyeondong, legal_dong_code) DO UPDATE
                            SET legal_dong_code = EXCLUDED.legal_dong_code
                        RETURNING id
                        """,
                        (prv_nm, sgg_nm, sgg_cd),
                    )
                    region_id = cur.fetchone()[0]

                    # 2) flood_history 테이블에 데이터 삽입
                    cur.execute(
                        """
                        INSERT INTO flood_history (
                            region_id,
                            event_date,
                            started_at,
                            ended_at,
                            flood_type,
                            depth_cm,
                            area_sqm,
                            source,
                            source_event_id,
                            geometry_wkt,
                            raw_payload
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, '생활안전지도', %s, %s, %s)
                        ON CONFLICT (source, source_event_id) DO UPDATE SET
                            region_id = EXCLUDED.region_id,
                            event_date = EXCLUDED.event_date,
                            started_at = EXCLUDED.started_at,
                            ended_at = EXCLUDED.ended_at,
                            flood_type = EXCLUDED.flood_type,
                            depth_cm = EXCLUDED.depth_cm,
                            area_sqm = EXCLUDED.area_sqm,
                            geometry_wkt = EXCLUDED.geometry_wkt,
                            raw_payload = EXCLUDED.raw_payload,
                            created_at = NOW()
                        """,
                        (
                            region_id,
                            event_date,
                            started_at,
                            ended_at,
                            fldn_dst_nm or fldn_cs_dtl_nm,
                            depth_cm,
                            area_sqm,
                            source_event_id,
                            geom_wkt,
                            json.dumps(item, ensure_ascii=False)
                        ),
                    )

                page_processed += 1
                total_processed += 1

            if not args.dry_run:
                conn.commit()
                print(f"Page {page_no} saved. Added {page_processed} records.")
            else:
                print(f"Page {page_no} dry-run complete. Filtered {page_processed} records.")

            # 다음 페이지 이동 조건
            if total_count > 0 and page_no * num_of_rows >= total_count:
                print("Reached total count limit.")
                break

            if args.limit_pages > 0 and page_no >= args.limit_pages:
                print(f"Reached page limit constraint: {args.limit_pages}")
                break

            page_no += 1

    finally:
        if conn:
            cur.close()
            conn.close()

    print("\n--- Ingestion Report ---")
    print(f"Total flood history records processed: {total_processed}")
    if args.dry_run:
        print("Dry-run mode: No database changes were made.")
    else:
        print("All records successfully written to PostgreSQL.")


if __name__ == "__main__":
    main()
