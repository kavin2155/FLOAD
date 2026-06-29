# FLOAD 데이터베이스 활용법

이 문서는 수집된 데이터를 확인하고, 추가로 적재하고, 학습용 CSV로 내보내는 방법을 정리합니다.

현재 DB에 저장하는 데이터는 다음과 같습니다.

- 기상청 강수량 데이터
- 과거 침수 이력 데이터
- CCTV/침수위험 이미지 메타데이터
- 침수/비침수 라벨

## DB 위치

DB는 두 가지로 나누어 사용합니다.

```text
로컬 Docker DB
- 개발/테스트용
- 스크립트가 제대로 동작하는지 먼저 확인

Supabase DB
- 팀 공유용 클라우드 DB
- 실제 누적 데이터 확인용
```

`.env`의 `DATABASE_URL`이 어디를 가리키는지에 따라 스크립트가 데이터를 넣는 위치가 달라집니다.

```text
로컬 Docker DB:
DATABASE_URL=postgresql://flood_user:flood_pass@localhost:5432/flood_ai

Supabase DB:
DATABASE_URL=postgresql://...
```

GitHub에는 `.env`를 올리지 않습니다.

## 기본 사용 순서

```text
1. DB 연결 상태 확인
2. 테이블별 데이터 수 확인
3. 필요한 데이터를 추가 수집/적재
4. 학습용 CSV export
```

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

## 빠른 점검

현재 연결된 DB가 살아 있는지 확인합니다.

```bash
.venv/bin/python scripts/check_database.py
```

테이블별 데이터 수를 SQL로 직접 확인할 수도 있습니다.

```bash
docker exec road-flood-postgres psql -U flood_user -d flood_ai -c "
SELECT 'cctv_media' AS table_name, COUNT(*) FROM cctv_media
UNION ALL SELECT 'flood_labels', COUNT(*) FROM flood_labels
UNION ALL SELECT 'rainfall_observations', COUNT(*) FROM rainfall_observations
UNION ALL SELECT 'flood_history', COUNT(*) FROM flood_history;
"
```

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

## 모델 학습용 데이터 export

모델 학습자는 DB를 직접 깊게 알 필요 없이 CSV를 받아서 시작할 수 있어야 합니다.
아래 명령은 `cctv_media`와 `flood_labels`를 조인해서 학습용 CSV를 만듭니다.

```bash
.venv/bin/python scripts/export_training_dataset.py
```

기본 출력 파일:

```text
outputs/training_dataset.csv
```

CSV 컬럼:

```text
media_id
file_path
label
captured_at
media_type
source_dataset
cctv_code
cctv_name
width
height
duration_sec
label_source
note
```

부산시 침수위험 복합 데이터만 뽑으려면:

```bash
.venv/bin/python scripts/export_training_dataset.py \
  --source-dataset 부산시_침수위험_복합_데이터
```

지능형 관제 CCTV 영상 데이터만 뽑으려면:

```bash
.venv/bin/python scripts/export_training_dataset.py \
  --source-dataset 지능형_관제_서비스_CCTV_영상_데이터
```

이 CSV가 모델 학습 코드의 첫 입력입니다.

중요한 점:

- 이미지/영상 파일 자체는 DB에 넣지 않습니다.
- DB에는 파일 경로와 라벨, 메타데이터를 저장합니다.
- 학습 코드는 CSV의 `file_path`를 보고 실제 이미지/영상 파일을 읽습니다.
- Supabase에는 대용량 이미지 파일이 아니라 메타데이터와 라벨을 저장합니다.

## 팀원이 처음 볼 때 이해해야 할 것

이 DB는 침수 탐지 모델 학습을 위해 다음 질문에 답하도록 설계되어 있습니다.

```text
1. 어떤 이미지/영상인가?
   cctv_media

2. 침수인지 아닌지 라벨은 무엇인가?
   flood_labels

3. 해당 시점에 비가 얼마나 왔는가?
   rainfall_observations

4. 해당 지역의 과거 침수 이력은 있는가?
   flood_history
```

처음 학습은 `cctv_media + flood_labels`만으로 시작할 수 있습니다.
이후 성능을 높이기 위해 강수량, 침수 이력, 수위 데이터를 추가로 연결합니다.
