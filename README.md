# FLOAD DB

## Docker 실행

```bash
docker compose up -d
```

## DB 접속

```bash
docker exec -it road-flood-postgres psql -U flood_user -d flood_ai
```

외부 툴에서 접속할 때는 아래 값을 사용한다.

```text
host: localhost
port: 5432
database: flood_ai
user: flood_user
password: flood_pass
```

## 스키마 적용

이미 Docker volume이 만들어진 뒤에는 `db/schema.sql`이 자동 실행되지 않는다.
스키마를 새로 적용하려면 아래 명령을 실행한다.

```bash
docker exec -i road-flood-postgres psql -U flood_user -d flood_ai < db/schema.sql
```

## 현재 테이블

- `regions`: 행정구역/좌표
- `weather_stations`: 기상 관측소
- `rainfall_observations`: 실시간/과거 강수량 관측값
- `flood_history`: 침수흔적도/과거 침수 이력
- `cctv_sources`: CCTV 위치/출처
- `cctv_media`: CCTV 이미지/영상 파일 메타데이터
- `flood_labels`: 정상/침수직전/침수 라벨
- `collection_runs`: 수집 작업 실행 기록

## 기상청 강수량 수집

`.env.example`을 복사해서 `.env` 파일을 만들고, 발급받은 키를 넣는다.

```bash
cp .env.example .env
```

```text
KMA_API_KEY=발급받은_기상청_api키
DATABASE_URL=postgresql://flood_user:flood_pass@localhost:5432/flood_ai
```

필요한 Python 패키지를 설치한다.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

실시간/최근 시간자료는 `kma_sfctm2.php`를 사용한다.

```bash
.venv/bin/python scripts/collect_kma_rainfall.py --mode realtime --station 0
```

과거 기간자료는 `kma_sfctm3.php`를 사용한다.

```bash
.venv/bin/python scripts/collect_kma_rainfall.py \
  --mode period \
  --start 202406010000 \
  --end 202406012300 \
  --station 0
```

`--start`, `--end`는 한국시간 기준 `YYYYMMDDHHMM` 형식이다.
DB의 `observed_at`은 `timestamptz`라서 조회할 때 UTC로 보일 수 있다.
예를 들어 `2026-06-27 15:00:00+00`은 한국시간 `2026-06-28 00:00`이다.

처음에는 DB에 넣지 않고 API 응답 파싱만 확인할 수 있다.

```bash
.venv/bin/python scripts/collect_kma_rainfall.py \
  --mode period \
  --start 202406010000 \
  --end 202406010100 \
  --station 0 \
  --dry-run
```

## CCTV 메타데이터 및 라벨 적재

AI Hub에서 다운로드한 `07.지능형_관제_서비스_CCTV_영상_데이터` 데이터셋의 JSON 라벨 데이터를 파싱하여 DB에 적재한다.
대용량 비디오 파일(.mp4)을 일일이 압축 해제할 필요 없이, 메모리 상에서 직접 라벨 압축 파일(`TL_...zip.part0`)을 파싱하여 가상의 경로로 DB에 고속 적재한다.

### 1. 환경 설정 (.env)

`.env` 파일에 AI Hub 데이터셋이 저장된 루트 경로인 `DATASET_DIR` 변수를 등록한다.

```text
DATASET_DIR=/Users/사용자명/Downloads/07.지능형_관제_서비스_CCTV_영상_데이터
```

### 2. 적재기 실행

동작 검증을 위해 DB에 반영하지 않고 파싱 결과만 확인하려면 `--dry-run` 옵션을 붙여 실행한다.

```bash
.venv/bin/python scripts/ingest_cctv_dataset.py --dry-run
```

실제 데이터베이스에 반영하려면 옵션 없이 실행한다.

```bash
.venv/bin/python scripts/ingest_cctv_dataset.py
```

## 침수흔적도 데이터 수집

생활안전지도 API(DSSP-IF-00117)를 연동하여 침수 이력(`flood_history`) 테이블에 데이터를 수집 및 적재한다.

### 1. 환경 설정 (.env)

`.env` 파일에 생활안전지도 API 키 `SAFETY_DATA_API_KEY` 변수를 등록한다.

```text
SAFETY_DATA_API_KEY=발급받은_서비스키
```

### 2. 수집기 실행

기본값으로 **부산광역시** 지역 데이터만 필터링하여 수집하도록 설정되어 있다.

동작 검증을 위해 DB에 반영하지 않고 파싱 결과만 확인하려면 `--dry-run` 옵션을 붙여 실행한다.

```bash
.venv/bin/python scripts/collect_flood_history.py --dry-run
```

전체 지역 데이터를 조회하며 파싱 결과를 보려면 `--all-regions` 옵션을 함께 사용한다.

```bash
.venv/bin/python scripts/collect_flood_history.py --dry-run --all-regions --limit-pages 1
```

실제 데이터베이스에 반영하여 수집을 진행하려면 옵션 없이 실행한다.

```bash
.venv/bin/python scripts/collect_flood_history.py
```

## 부산시 침수위험 복합 데이터 적재

AI Hub의 **부산시 침수위험 복합 데이터(수치모델 침수 이미지)**의 라벨 데이터셋(Training/Validation)을 파싱하여 데이터베이스에 일괄 적재한다.

### 1. 데이터셋 디렉토리 설정
`.env` 파일에 데이터셋 루트 폴더의 절대 경로를 `DATASET_DIR` 또는 직접 명령 인자로 넘겨줄 수 있다. 기본 디렉토리는 `/Users/jeong-yunhwan/Downloads/135.부산시_침수위험_복합_데이터`로 설정되어 있다.

### 2. 적재 실행
실제 DB 반영 전에 파싱이 잘 돌아가는지 테스트하려면 `--dry-run` 옵션을 사용한다.

```bash
.venv/bin/python scripts/ingest_flood_risk_dataset.py --dry-run
```

실제 DB에 일괄 인서트하려면 옵션 없이 실행한다.
기본값은 `.env`의 `DATABASE_URL`을 사용하므로, 로컬 Docker DB와 Supabase 중 어느 DB에 넣을지 먼저 확인한다.

```bash
.venv/bin/python scripts/ingest_flood_risk_dataset.py
```

## Supabase 클라우드 DB 마이그레이션

Supabase 접속 문자열은 GitHub에 올리지 않고 `.env`에만 저장한다.

```text
SUPABASE_DATABASE_URL=postgresql://postgres.project-ref:비밀번호@host:6543/postgres
```

로컬 Docker DB의 데이터를 Supabase로 복사하려면 아래 명령을 실행한다.

```bash
.venv/bin/python scripts/migrate_to_cloud.py
```
