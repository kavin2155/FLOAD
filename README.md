# FLOAD 데이터 사용 안내

FLOAD는 CCTV 기반 침수 탐지 AI 모델을 만들기 위한 프로젝트입니다.

이 저장소는 팀원이 같은 데이터를 기준으로 학습 데이터를 확인하고, 필요한 파일 위치를 빠르게 찾을 수 있도록 정리한 안내서와 수집 코드를 담고 있습니다.

## 먼저 볼 것

팀원이 데이터를 확인할 때는 아래 스프레드시트를 먼저 보면 됩니다.

[FLOAD_데이터_현황](https://docs.google.com/spreadsheets/d/1gx7EI8ngK-dSwvHW3d5Qm97ClD4If218TXkIbfXORlo/edit?usp=drivesdk)

스프레드시트에는 현재 수집된 강수량, 침수이력, 데이터 수집 현황이 정리되어 있습니다.

```text
README_사용법
수집현황
실시간_강수량
과거강수량_시간별
과거강수량_일별요약
침수이력_API전체
```

## 데이터 파일 위치

CCTV 영상, 이미지, 라벨 파일처럼 용량이 큰 원본 데이터는 아래 Google Drive 폴더에 있습니다.

[FLOAD_DATA](https://drive.google.com/drive/folders/1DxYZwzf4QliiFzZdf32HQ6U0sHpMQBnC)

현재 Drive 구조는 아래처럼 나눠져 있습니다.

```text
FLOAD_DATA/
  raw/
    07_cctv/original/
    135_busan_flood/original/
  processed/
  exports/
  docs/
```

## Drive에 있는 CCTV 데이터

`raw/07_cctv/original/`

도로 CCTV 기반 침수 탐지 학습에 사용할 수 있는 원본 영상/라벨 데이터입니다.
침수 여부를 판단하는 모델을 만들 때 영상 프레임 추출, 라벨 확인, 학습용 이미지 생성의 기준 데이터로 사용합니다.

`raw/135_busan_flood/original/`

부산 지역 침수위험 복합 데이터입니다.
부산으로 지역을 좁혀 침수 탐지 모델을 학습할 때 사용할 원본 이미지/라벨/메타데이터가 들어가는 위치입니다.

`processed/`

원본 데이터를 학습에 바로 쓰기 좋게 가공한 결과물을 둘 위치입니다.
예를 들면 프레임 추출 이미지, 정리된 라벨, train/valid/test 분할 파일을 여기에 둡니다.

`exports/`

팀원이 표로 확인할 수 있는 파일을 두는 위치입니다.
현재 데이터 현황 스프레드시트도 이 기준으로 관리합니다.

`docs/`

데이터 설명서, 수집 기준, 참고 문서를 두는 위치입니다.

## 스프레드시트에 있는 데이터

`수집현황`

현재 어떤 데이터가 수집되었고, 어떤 데이터가 아직 진행 중인지 확인하는 탭입니다.

`실시간_강수량`

부산 강수량을 실시간으로 수집한 결과를 확인하는 탭입니다.
CCTV 침수 장면과 같은 시간대의 비 정보를 맞춰볼 때 사용합니다.

`과거강수량_시간별`

부산 과거 강수량을 시간 단위로 정리한 탭입니다.
침수 이미지나 영상이 촬영된 날짜와 시간에 비가 얼마나 왔는지 확인할 때 사용합니다.

`과거강수량_일별요약`

시간별 강수량을 날짜별로 요약한 탭입니다.
특정 날짜가 침수 가능성이 높은 날이었는지 빠르게 보는 용도입니다.

`침수이력_API전체`

부산 침수흔적도 데이터를 정리한 탭입니다.
부산 내 어떤 구/군에서 침수 이력이 있었는지 확인하고, CCTV 데이터와 지역 기준을 맞출 때 사용합니다.

## 팀원이 데이터를 쓰는 흐름

1. [FLOAD_데이터_현황](https://docs.google.com/spreadsheets/d/1gx7EI8ngK-dSwvHW3d5Qm97ClD4If218TXkIbfXORlo/edit?usp=drivesdk)에서 현재 수집된 데이터를 확인합니다.
2. 필요한 원본 파일은 [FLOAD_DATA](https://drive.google.com/drive/folders/1DxYZwzf4QliiFzZdf32HQ6U0sHpMQBnC)의 `raw/`에서 찾습니다.
3. 모델 학습에 바로 쓸 수 있게 가공한 파일은 `processed/`에 정리합니다.
4. 팀원이 같이 봐야 하는 표나 CSV는 `exports/`에 둡니다.
5. 데이터 설명서나 기준 문서는 `docs/`에 둡니다.

## GitHub에는 무엇을 두는가

GitHub에는 대용량 원본 영상이나 이미지를 올리지 않습니다.

GitHub에는 아래 내용만 둡니다.

```text
데이터 수집 코드
데이터 사용 설명
폴더 구조 설명
작업 기록
```

즉, 실제 데이터 파일은 Google Drive에서 보고, GitHub는 프로젝트 사용법과 코드 관리용으로 사용합니다.

## 현재 기준

현재 프로젝트는 부산 지역을 우선 대상으로 잡고 있습니다.

이유는 부산 침수위험 데이터와 CCTV 데이터를 같은 지역 기준으로 맞추면, 모델 학습에 필요한 이미지, 시간, 위치, 강수량 정보를 더 일관되게 연결할 수 있기 때문입니다.

```text
우선 지역: 부산
주요 목표: CCTV 기반 침수/비침수 판단
보조 데이터: 강수량, 침수이력, 촬영 시각, 지역 정보
```

## 공유 권한

Google Drive와 스프레드시트는 링크가 있는 모든 사용자가 볼 수 있도록 설정되어 있습니다.

팀원에게는 아래 두 링크를 공유하면 됩니다.

```text
데이터 현황표:
https://docs.google.com/spreadsheets/d/1gx7EI8ngK-dSwvHW3d5Qm97ClD4If218TXkIbfXORlo/edit?usp=drivesdk

데이터 폴더:
https://drive.google.com/drive/folders/1DxYZwzf4QliiFzZdf32HQ6U0sHpMQBnC
```
