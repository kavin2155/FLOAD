#!/usr/bin/env python3
import json
import os
import re
from pathlib import Path
import psycopg

DEFAULT_LOCAL_URL = "postgresql://flood_user:flood_pass@localhost:5432/flood_ai"
REMOTE_URL = "postgresql://postgres.hasogtetrgtthutntsla:wjddbsghks1!@aws-1-ap-northeast-1.pooler.supabase.com:6543/postgres"


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def run_schema(cur_remote, schema_path: Path) -> None:
    print(f"Applying schema from {schema_path} to remote Supabase DB...")
    sql_content = schema_path.read_text(encoding="utf-8")
    
    # schema.sql의 개별 DDL 문 실행
    # psycopg 3에서는 단일 execute로 세미콜론 구분 쿼리 묶음을 실행할 수 있습니다.
    cur_remote.execute(sql_content)
    print("Schema applied successfully.")


def migrate_table(cur_local, cur_remote, table_name: str) -> None:
    print(f"Migrating table: {table_name}...")
    
    # 1. 로컬 테이블 데이터 조회
    cur_local.execute(f"SELECT * FROM {table_name};")
    rows = cur_local.fetchall()
    
    if not rows:
        print(f"Table {table_name} is empty in local DB. Skipping.")
        return
        
    # 컬럼 이름 추출
    colnames = [desc[0] for desc in cur_local.description]
    columns_str = ", ".join(colnames)
    placeholders = ", ".join(["%s"] * len(colnames))
    
    # 2. 원격 테이블에 데이터 삽입 (기존 ID 유지, 충돌 시 무시)
    query = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders}) ON CONFLICT DO NOTHING;"
    
    inserted = 0
    for row in rows:
        adapted_row = []
        for val in row:
            if isinstance(val, dict):
                adapted_row.append(json.dumps(val, ensure_ascii=False))
            else:
                adapted_row.append(val)
        cur_remote.execute(query, adapted_row)
        inserted += 1
        
    print(f"Transferred {inserted} records into remote {table_name}.")

    # 3. ID 시퀀스 초기화 (다음 INSERT 시 시퀀스 꼬임 방지)
    # id 컬럼이 있는 테이블만 시퀀스 업데이트 실행
    if "id" in colnames:
        seq_query = f"SELECT setval('{table_name}_id_seq', COALESCE((SELECT MAX(id)+1 FROM {table_name}), 1), false);"
        try:
            cur_remote.execute(seq_query)
        except Exception as e:
            # 시퀀스가 존재하지 않는 등 예외 발생 시 무시
            pass


def main() -> None:
    load_dotenv(Path(".env"))
    
    local_url = os.environ.get("DATABASE_URL", DEFAULT_LOCAL_URL)
    remote_url = REMOTE_URL

    print("Connecting to local and remote databases...")
    
    # 두 DB 연결
    with psycopg.connect(local_url) as conn_local, psycopg.connect(remote_url) as conn_remote:
        with conn_local.cursor() as cur_local, conn_remote.cursor() as cur_remote:
            
            # 1. 원격 DB에 스키마 생성
            schema_path = Path("db/schema.sql")
            run_schema(cur_remote, schema_path)
            conn_remote.commit()
            
            # 2. 테이블 리스트 순차 마이그레이션 (외래키 순서 준수)
            tables = [
                "regions",
                "weather_stations",
                "rainfall_observations",
                "flood_history",
                "cctv_sources",
                "cctv_media",
                "flood_labels",
                "collection_runs"
            ]
            
            for table in tables:
                migrate_table(cur_local, cur_remote, table)
                conn_remote.commit()
                
            print("\nDatabase migration completed successfully!")


if __name__ == "__main__":
    main()
