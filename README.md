# FLOAD 데이터 관리 방법

이 저장소는 침수 탐지 AI 모델 학습에 필요한 데이터를 관리하기 위한 코드와 사용법을 담습니다.

역할은 단순하게 나눕니다.

```text
Google Drive
- AI Hub 이미지/영상 원본 파일
- AI Hub 라벨 JSON
- 학습용 CSV

Supabase
- 기상청 강수량 API 데이터
- 침수흔적도 API 데이터

GitHub
- 수집 코드
- 사용 설명서
- DB 스키마
```

## Google Drive 데이터 폴더

프로젝트 데이터 파일은 아래 Google Drive 폴더에 둡니다.

```text
FLOAD_DATA
https://drive.google.com/drive/folders/1DxYZwzf4QliiFzZdf32HQ6U0sHpMQBnC
```

현재 폴더 구조:

```text
FLOAD_DATA/
  raw/
    07_cctv/
    135_busan_flood/
  processed/
  exports/
  docs/
```

AI Hub에서 받은 대용량 파일은 GitHub나 Supabase DB에 올리지 않습니다.
Google Drive의 `raw/` 아래에 보관합니다.

## Supabase에 저장하는 데이터

Supabase에는 API로 수집한 정형 데이터만 저장합니다.

```text
regions
weather_stations
rainfall_observations
flood_history
collection_runs
```

이미지/영상/라벨 JSON 원본은 Supabase DB에 저장하지 않습니다.

## 환경 설정

`.env.example`을 복사해서 `.env` 파일을 만듭니다.

```bash
cp .env.example .env
```

`.env`에 Supabase 접속 문자열과 API 키를 넣습니다.

```text
DATABASE_URL=postgresql://postgres.project-ref:비밀번호@host:6543/postgres
KMA_API_KEY=기상청_API_KEY
SAFETY_DATA_API_KEY=생활안전지도_API_KEY
DATASET_DIR=/Google_Drive/FLOAD_DATA
```

`.env`는 GitHub에 올리지 않습니다.

## 패키지 설치

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## DB 상태 확인

```bash
.venv/bin/python scripts/check_database.py
```

## 기상청 강수량 수집

부산 대표 관측소 `159` 기준으로 수집합니다.

실시간/최근 시간자료 테스트:

```bash
.venv/bin/python scripts/collect_kma_rainfall.py --mode realtime --station 159 --dry-run
```

Supabase에 저장:

```bash
.venv/bin/python scripts/collect_kma_rainfall.py --mode realtime --station 159
```

과거 기간자료 저장:

```bash
.venv/bin/python scripts/collect_kma_rainfall.py \
  --mode period \
  --start 202406010000 \
  --end 202406012300 \
  --station 159
```

`--start`, `--end`는 한국시간 기준 `YYYYMMDDHHMM` 형식입니다.

## 실시간 강수량 자동 수집

macOS에서 매시간 5분에 부산 실시간 강수량을 Supabase에 저장하도록 설정할 수 있습니다.

```bash
.venv/bin/python scripts/install_realtime_rainfall_job.py
```

설치 후 로그는 아래 파일에서 확인합니다.

```text
logs/realtime_rainfall.out.log
logs/realtime_rainfall.err.log
```

## 침수흔적도 데이터 수집

생활안전지도 API 데이터를 `flood_history` 테이블에 저장합니다.
기본값은 부산 데이터만 수집합니다.

테스트:

```bash
.venv/bin/python scripts/collect_flood_history.py --dry-run
```

저장:

```bash
.venv/bin/python scripts/collect_flood_history.py
```

## AI Hub 데이터 사용

AI Hub 이미지/영상/라벨 JSON은 Google Drive에 보관합니다.
모델 학습 시에는 Google Drive에서 내려받은 파일과 별도 학습용 CSV를 사용합니다.

권장 방식:

```text
1. Google Drive에서 FLOAD_DATA를 내려받음
2. DATASET_DIR을 FLOAD_DATA 경로로 설정
3. exports/ 아래의 학습용 CSV를 사용
4. CSV의 상대경로를 DATASET_DIR에 붙여 이미지/영상 파일을 읽음
```

## 요약

```text
큰 파일 = Google Drive
API 데이터 = Supabase
코드/문서 = GitHub
```
