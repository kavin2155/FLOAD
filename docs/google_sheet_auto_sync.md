# Google Sheets 자동갱신 설정

실시간 강수량은 먼저 Supabase/PostgreSQL DB에 저장되고, 그 다음 Google Sheets의 `실시간_강수량` 시트로 동기화됩니다.

## 현재 자동 실행 흐름

매시간 5분에 macOS LaunchAgent가 아래 파이프라인을 실행합니다.

```bash
.venv/bin/python scripts/run_realtime_rainfall_pipeline.py
```

파이프라인은 두 단계를 순서대로 실행합니다.

1. 기상청 API에서 부산 관측소 강수량을 수집합니다.
2. DB에 저장된 최신 실시간 강수량을 Google Sheets에 반영합니다.

## Google Sheets 동기화에 필요한 것

자동으로 Google Sheets에 쓰려면 Google 서비스 계정 JSON 파일이 필요합니다.

1. Google Cloud에서 서비스 계정을 만듭니다.
2. 서비스 계정 키를 JSON으로 다운로드합니다.
3. 대상 Google Sheet를 서비스 계정 이메일에 공유합니다.
   - 권한: 편집자
4. `.env`에 아래 값을 추가합니다.

```bash
GOOGLE_SERVICE_ACCOUNT_JSON=/absolute/path/to/google-service-account.json
GOOGLE_SHEET_ID=1gx7EI8ngK-dSwvHW3d5Qm97ClD4If218TXkIbfXORlo
GOOGLE_REALTIME_RAINFALL_SHEET_NAME=실시간_강수량
```

`GOOGLE_SERVICE_ACCOUNT_JSON`이 없으면 DB 저장은 계속 진행되고, Google Sheets 동기화만 건너뜁니다.

## 수동 실행

설정 후 바로 확인하려면 아래 명령을 실행합니다.

```bash
.venv/bin/python scripts/run_realtime_rainfall_pipeline.py
```

Google Sheets 동기화만 따로 확인하려면 아래 명령을 실행합니다.

```bash
.venv/bin/python scripts/sync_realtime_rainfall_to_sheet.py
```
