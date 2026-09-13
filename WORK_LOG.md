# 명예회장봇 작업 기록

이 파일은 명예회장봇의 모든 작업 내역을 관리하는 단일 Markdown 기록입니다. 앞으로 작업을 수행할 때마다 이 파일에 날짜, 변경 내용, 검증 결과를 추가합니다.

## 2026-09-13 — 저장소 연동 및 초기 점검

### 작업 내용

- GitHub 저장소 `Kimmacaroni/myhjbb-`를 작업 환경으로 가져왔습니다.
- `main` 브랜치를 기준으로 동기화했습니다.
- 확인한 최신 커밋: `37f94e2` — `Restore manual-only menu workflow to avoid duplicate sends`

### 현재 구성

- `food_bot.py`: 봇의 주 실행 코드
- `menu_source.py`: 식단 정보 수집/처리 코드
- `config.py`: 환경 설정
- `requirements.txt`: Python 의존성 목록
- `[명예회장봇] 푸드피아 식단`: 식단 데이터

### 검증

- 원격 저장소 SSH 접근 확인 완료
- 로컬 브랜치: `main` (`origin/main` 추적)

### 운영 원칙

- 작업 기록은 이 `WORK_LOG.md` 한 파일에만 누적합니다.
- 코드·설정·데이터 변경 시 작업 목적, 변경 사항, 검증 결과를 함께 기록합니다.

## 2026-09-13 — 가동 중인 Discord 명령어 점검

### 확인 결과

- VPS의 `honorary-bot.service`가 정상 실행 중입니다.
- 실제 실행 위치는 `/opt/honorary-bot`이며 `bot.py`가 상시 실행되고 있습니다.
- 등록된 Discord 슬래시 명령어는 총 **32개**입니다.

### 명령어 구성

- 경험치·랭킹: 5개
- 칭호: 4개
- 식단: 4개
- 교통정보: 5개
- 음악: 10개
- 음성(TTS): 1개
- 업데이트: 2개
- 도움말: 1개

### 참고

- GitHub `main`의 간소화된 식단 전송 스크립트만으로 명령어 수를 판단하면 안 됩니다.
- 실제 상시 Discord 봇 소스는 VPS의 `/opt/honorary-bot`에 배포되어 있으며, 해당 소스를 기준으로 명령어 수를 확인했습니다.
