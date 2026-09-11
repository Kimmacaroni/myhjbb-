# 기능 소유권 지도

## 운영 기준과 경계

- **공식 운영 본체는 VPS에서 `bot.py`로 실행하는 Discord Gateway 봇**이다. `bot.py`가 아래 7개 Cog를 extension으로 로드하며, 음성 연결·자동 경험치·정기 작업을 포함한 전체 기능을 소유한다.
- `cloudflare/`는 HTTP interaction과 cron을 제공하는 **보조 구현**이다. VPS의 음악, TTS, 음성 상태, Gateway 이벤트를 대체하지 않으며 임의 삭제·통합 대상이 아니다.
- `food_bot.py`와 `.github/workflows/main.yml`은 식단만 한 번 전송하는 선택적 GitHub Actions 경로다. VPS 식단 작업과 동시에 켜면 중복 전송될 수 있다.

## VPS 기능별 소유권

| 기능 | 진입/명령 | 주 소유 파일 | 공통 의존성·영구 상태 |
|---|---|---|---|
| 시작·명령 동기화 | `python bot.py` | `bot.py` | `config.py`, `db.py` |
| 경험치·레벨 | `/경험치`, `/랭킹`, XP 조정; 채팅/음성 이벤트 | `cogs/leveling.py` | `levels.py`, `access_control.py`, SQLite `users` |
| 칭호 | `/칭호추가` 등 4개 | `cogs/titles.py` | `access_control.py`, SQLite `titles` |
| 식단 | `/식단` 등 4개; 매일 전송 | `cogs/menu.py` | `menu_source.py`, SQLite `guild_settings.menu_channel_id` |
| 교통 | `/교통정보` 등 5개; 주기 알림 | `cogs/traffic.py` | `traffic_source.py`, SQLite `guild_settings`, `traffic_seen_incidents`, `bot_settings` |
| 음악 | `/재생` 등 10개; 대시보드 | `cogs/music.py` | `music_helpers.py`, `voice_playback.py`, `voice_idle.py`, FFmpeg/yt-dlp, 선택 쿠키 |
| 한국어 TTS | `/음성` | `cogs/tts.py` | `experimental/huggingface_korean_tts.py`, `voice_playback.py`, `voice_idle.py`, VPS 모델 |
| 도움말 | `/도움말` | `cogs/help.py` | 실제 command tree와 `access_control.py` |

`access_control.py`의 소유자 예외는 `BOT_OWNER_IDS`(쉼표 또는 공백 구분)에서만 읽는다. 미설정 또는 잘못된 값은 예외 권한을 부여하지 않는 fail-closed 동작이다.

## Cloudflare 보조 범위

- `cloudflare/src/index.ts`, `interactions.ts`: Discord HTTP interaction 검증·라우팅
- `cloudflare/src/commands/`: 레벨/칭호/식단/교통/도움말의 서버리스 명령 일부
- `cloudflare/src/scheduled.ts`: 식단·교통 cron
- `cloudflare/src/db.ts`, `migrations/`: D1 데이터
- `cloudflare/test/`: 보조 구현 회귀 테스트
- 음악·TTS·Gateway 자동 경험치는 Cloudflare 범위가 아니다.

## 영구·민감 데이터

배포와 소스 관리에서 `.env`, `*.db`(특히 `bot.db`), `youtube-cookies.txt`, `cookies/`, `models/`를 보존·제외한다. 소스에는 값이 비어 있는 `.env.example`만 둔다. VPS 파일의 내용·소유권·권한을 로컬 사본으로 덮어쓰지 않는다.

## 구조 변경 원칙

1. `bot.py`의 Cog 로드 목록과 각 Cog의 명령 등록을 먼저 확인한다.
2. 제거는 저장소 참조 0건과 테스트/정적 검증 근거가 모두 있을 때만 한다.
3. 기능별 Cog 경계와 `cloudflare/` 보조 구현은 유지한다.
4. 음악/TTS처럼 외부 서비스가 필요한 경로는 작은 순수 헬퍼를 우선 추출하고 단위 테스트한다.
5. VPS 접속·push·배포는 각각 별도 명시 승인이 있을 때만 한다.

## 검증 명령

```bash
python3 scripts/verify_structure.py
python3 -m unittest discover -s tests -v
python3 -m compileall -q -x '(^|/)(\.git|\.venv|venv|models)(/|$)' .
(cd cloudflare && npm test)
git diff --check
git diff --cached --check
```

구조 검증은 VPS Cog 7개, 슬래시 명령 30개, Cloudflare 핵심 파일, 영구 데이터 ignore 규칙, `access_control.py`의 하드코딩 Discord ID 부재를 확인한다.
