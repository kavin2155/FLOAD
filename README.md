# FLOAD 데이터베이스 활용법

이 문서는 Supabase 클라우드 DB에 저장된 데이터를 확인하고, 추가로 적재하고, 학습용 CSV로 내보내는 방법을 정리합니다.

## 기본 구조

데이터는 Supabase PostgreSQL에 저장합니다.

```text
Supabase
└── PostgreSQL
    ├── regions
    ├── weather_stations
    ├── rainfall_observations
    ├── flood_history
    ├── cctv_sources
    ├── cctv_media
    ├── flood_labels
    └── collection_runs
```

이미지/영상 파일 자체를 DB에 넣지는 않습니다.
DB에는 파일 경로, 라벨, 촬영 시각, 원본 메타데이터를 저장합니다.

## 환경 설정

`.env.example`을 복사해서 `.env` 파일을 만듭니다.

```bash
cp .env.example .env
```

`.env`에는 Supabase 접속 문자열과 필요한 API 키를 넣습니다.

```text
DATABASE_URL=postgresql://postgres.project-ref:비밀번호@host:6543/postgres
KMA_API_KEY=기상청_API_KEY
SAFETY_DATA_API_KEY=생활안전지도_API_KEY
DATASET_DIR=/AI_Hub_데이터셋_경로
```

`.env`는 GitHub에 올리지 않습니다.

## 패키지 설치

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## DB 상태 확인

Supabase DB 연결과 테이블별 데이터 수를 확인합니다.

```bash
.venv/bin/python scripts/check_database.py
```

현재 주요 테이블의 의미는 다음과 같습니다.

- `regions`: 행정구역 정보
- `weather_stations`: 기상 관측소 정보
- `rainfall_observations`: 시간별 강수량
- `flood_history`: 과거 침수 이력
- `cctv_sources`: CCTV 또는 이미지 출처 지점
- `cctv_media`: 이미지/영상 파일 경로와 메타데이터
- `flood_labels`: 침수/비침수 라벨
- `collection_runs`: 수집 작업 기록

## 기상청 강수량 수집

실시간/최근 시간자료는 `kma_sfctm2.php`를 사용합니다.

```bash
.venv/bin/python scripts/collect_kma_rainfall.py --mode realtime --station 159 --dry-run
```

문제가 없으면 `--dry-run`을 빼고 Supabase에 저장합니다.

```bash
.venv/bin/python scripts/collect_kma_rainfall.py --mode realtime --station 159
```

과거 기간자료는 `kma_sfctm3.php`를 사용합니다.

```bash
.venv/bin/python scripts/collect_kma_rainfall.py \
  --mode period \
  --start 202406010000 \
  --end 202406012300 \
  --station 159
```

`--start`, `--end`는 한국시간 기준 `YYYYMMDDHHMM` 형식입니다.

## 침수흔적도 데이터 수집

생활안전지도 API 데이터를 `flood_history` 테이블에 저장합니다.
기본값은 부산 데이터만 수집하도록 되어 있습니다.

```bash
.venv/bin/python scripts/collect_flood_history.py --dry-run
```

문제가 없으면 `--dry-run`을 빼고 저장합니다.

```bash
.venv/bin/python scripts/collect_flood_history.py
```

## CCTV 메타데이터 및 라벨 적재

AI Hub `07.지능형_관제_서비스_CCTV_영상_데이터`의 라벨 JSON을 읽어
`cctv_media`, `flood_labels` 테이블에 저장합니다.

```bash
.venv/bin/python scripts/ingest_cctv_dataset.py --dry-run
```

문제가 없으면 실제로 저장합니다.

```bash
.venv/bin/python scripts/ingest_cctv_dataset.py
```

## 부산시 침수위험 복합 데이터 적재

AI Hub `135.부산시_침수위험_복합_데이터`의 라벨 JSON을 읽어
`cctv_media`, `flood_labels` 테이블에 저장합니다.

```bash
.venv/bin/python scripts/ingest_flood_risk_dataset.py --dry-run
```

문제가 없으면 실제로 저장합니다.

```bash
.venv/bin/python scripts/ingest_flood_risk_dataset.py
```

## 학습용 CSV 내보내기

모델 학습자는 DB를 직접 다루지 않고 CSV부터 사용할 수 있습니다.
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

특정 데이터셋만 내보낼 수도 있습니다.

```bash
.venv/bin/python scripts/export_training_dataset.py \
  --source-dataset 지능형_관제_서비스_CCTV_영상_데이터
```

```bash
.venv/bin/python scripts/export_training_dataset.py \
  --source-dataset 부산시_침수위험_복합_데이터
```

## 사용 순서 요약

```text
1. .env에 Supabase DATABASE_URL 설정
2. scripts/check_database.py로 DB 상태 확인
3. 필요한 수집/적재 스크립트 실행
4. scripts/export_training_dataset.py로 학습용 CSV 생성
5. CSV의 file_path와 label을 사용해 모델 학습
```
