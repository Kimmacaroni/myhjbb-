# 명예회장봇 v2

KD 사우 가족 디스코드 서버를 위한 봇입니다. 식단 자동 알림에서 시작해,
서버 운영에 흔히 필요한 경험치/레벨, 환영 메시지, 기본 모더레이션까지 포함합니다.

## 기능

| 분류 | 기능 |
| --- | --- |
| 식단 | 매일 정해진 시각(KST)에 지정 채널로 오늘의 식단 자동 전송 |
| 레벨 | 채팅/통화 경험치 적립, 레벨업 알림, 레벨 달성 시 역할 자동 지급/회수 |
| 모더레이션 | `/kick` `/ban` `/timeout` `/warn` `/warnings` `/clear` |
| 환영 | 신규 멤버 입장 시 환영 메시지 |
| 정보 | `/serverinfo` `/userinfo` `/level` `/leaderboard` `/help` |

## 두 가지 실행 방식

- **`bot.py`** — 상시 실행. 레벨/모더레이션/환영처럼 계속 이벤트를 지켜봐야 하는
  기능은 전부 이 방식이 필요합니다. 서버, VPS, 컨테이너 등 24시간 켜둘 수 있는
  곳에 올리세요. GitHub Actions는 실행 시간에 제한이 있어 상시 실행에는
  적합하지 않습니다.
- **`food_bot.py`** — GitHub Actions로 필요할 때만 한 번 실행해 식단만 보내는
  단발 스크립트입니다. `.github/workflows/main.yml`에서 수동 실행할 수
  있습니다(자동 스케줄은 꺼져 있음, 코드 내 주석 참고).

## 로컬에서 실행하기

```bash
pip install -r requirements.txt
cp .env.example .env   # 값을 채운 뒤
python bot.py
```

## 필요한 환경변수

전체 목록과 기본값은 `config.py`와 `.env.example`을 참고하세요. 필수는
`DISCORD_TOKEN` 하나뿐이고, 나머지는 해당 기능을 켜고 싶을 때만 채우면 됩니다.
(예: `MENU_CHANNEL_ID`를 안 채우면 식단 기능이, `WELCOME_CHANNEL_ID`를 안 채우면
환영 메시지가 자동으로 꺼집니다.)

`LEVEL_ROLES`는 레벨 달성 시 지급할 디스코드 역할 ID를 연결합니다. 역할은
디스코드 서버에서 미리 만들어 두어야 합니다.

```
LEVEL_ROLES=5:123456789012345678,10:234567890123456789
```

## 디스코드 개발자 포털 설정

1. https://discord.com/developers/applications 에서 애플리케이션(봇) 생성
2. **Bot > Privileged Gateway Intents**에서 **SERVER MEMBERS INTENT**를 켭니다.
   (환영 메시지, 통화방 인원 확인, 레벨 역할 지급에 필요합니다.)
3. **OAuth2 > URL Generator**에서 `bot`, `applications.commands` 스코프와
   필요한 권한(메시지 보내기, 역할 관리, 멤버 추방/차단, 메시지 관리 등)을 선택해
   생성된 링크로 서버에 초대합니다.

## 배포 시 참고

- `DB_PATH`가 가리키는 SQLite 파일은 재시작 후에도 남는 위치(영구 디스크)에
  있어야 경험치/경고 기록이 유지됩니다. 컨테이너를 매번 새로 만드는 방식이면
  볼륨을 마운트하세요.
- 여러 인스턴스를 동시에 띄우면 안 됩니다. 식단이 중복으로 올라가거나 경험치가
  중복 지급될 수 있습니다.
