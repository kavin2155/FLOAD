# 침수 탐지 AI + 우회경로 추천 시스템 DB

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
KMA_API_KEY=S8_gdZL6Sq-P4HWS-tqvZQ
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
