# 명예회장봇 → Hermes Agent / 하루 소프트웨어 랩 인수인계 문서

작성일: 2026-09-11 (KST)  
목적: 기존 Codex 대화에서 진행한 명예회장봇 개발·운영 작업을 다른 에이전트가 안전하게 이어받기 위한 통합 문서

> 보안 주의: 이 문서에는 Discord 토큰, API 키, YouTube 쿠키, VPS 비밀번호 및 개인 SSH 키를 넣지 않았다. 해당 값은 GitHub나 채팅에 붙여 넣지 말고 VPS의 `/opt/honorary-bot/.env`와 개인 PC의 안전한 저장소에서만 관리한다.

---

## 1. 프로젝트 개요

- 프로젝트명: 명예회장봇
- 종류: Python 기반 Discord 다기능 봇
- 주요 기능: 레벨/경험치, 칭호, 식단, 고속도로 교통정보, YouTube 음악 재생, 음악 대시보드, 한국어 TTS
- 원격 저장소: `https://github.com/Kimmacaroni/myhjbb-.git`
- 현재 공식 기준 브랜치: `claude/how-it-works-x3928d`
- 브랜치 정책: 당분간 `claude/how-it-works-x3928d`를 공식 기준으로 사용한다. `main`은 레거시이므로 기준으로 보거나 직접 전환하지 않으며, 변경을 독립 QA로 검증해 통합한 뒤 사용자가 명시적으로 승인한 경우에만 `main`을 공식 기준으로 전환한다.
- 로컬 작업 경로: `<로컬-worktree>`
- VPS 배포 경로: `/opt/honorary-bot`
- 서비스 이름: `honorary-bot.service`
- 서비스 관리자: systemd
- 현재 권장 운영 구조:
  - GitHub: 소스와 변경 이력 보관
  - Codex/Hermes Agent: 코드 수정과 검증
  - Hostinger VPS: Discord 봇 상시 실행
  - Cloudflare Worker: 상태 확인과 일부 보조 API
  - GitHub Actions: 필요 시 VPS 자동 배포

음악과 TTS는 지속적인 Discord 음성 연결, FFmpeg, Python 네이티브 패키지와 메모리가 필요하므로 Cloudflare Workers로 완전히 이전하지 않는다. 실제 봇 프로세스는 VPS에서 유지하는 것이 적합하다.

---

## 2. 인수인계 시 가장 먼저 할 일

GitHub 작업은 루트 [`AGENTS.md`](../AGENTS.md)의 작업·보안·배포 표준을 따르고, 시작과 완료 내역을 [`WORK_LOG.md`](WORK_LOG.md)에 기록한다.

1. 저장소를 열고 현재 브랜치와 변경 상태를 확인한다.
2. `git status`에서 사용자의 미커밋 변경이 있다면 절대 덮어쓰거나 초기화하지 않는다.
3. `README.md`, `.env.example`, 이 문서를 읽는다.
4. 로컬 수정과 검증을 먼저 수행한다. VPS 접속·검사·서비스 조작은 사용자의 명시적 배포 승인을 받은 뒤에만 한다.
5. 승인된 배포에서는 VPS의 `/opt/honorary-bot/.env` 존재 여부만 확인하되 비밀값을 출력하지 않고, `bot.db`를 덮어쓰지 않는지 확인한다.
6. 코드 수정 후 로컬 문법 검사를 수행한다. 승인된 배포에 한해 VPS 문법 검사, 서비스 재시작, 최근 로그 확인 순으로 검증한다.
7. 완료된 변경은 현재 작업 브랜치에 커밋한다. GitHub push와 배포는 각각 사용자의 명시적 승인을 받은 뒤에만 수행하며, 어느 한쪽의 승인을 다른 쪽 승인으로 간주하지 않는다.

절대로 하면 안 되는 작업:

- `.env`, Discord 토큰, YouTube 쿠키 파일, API 키를 GitHub에 커밋
- 사용자 확인 없이 `bot.db` 삭제 또는 교체
- `git reset --hard`로 사용자 변경 제거
- Cloudflare Workers에서 Discord 음성 봇을 상시 실행하려고 시도
- 운영 중인 봇을 장시간 중단한 채 검증 없이 배포

---

## 3. 주요 파일 구조

### 봇 본체

- `bot.py`: 봇 시작, Cog 로드, Discord 로그인 및 명령어 동기화
- `config.py`: 환경변수 기반 설정
- `db.py`: SQLite 데이터 저장과 서버별 설정
- `access_control.py`: 관리자 권한 및 봇 소유자 예외 처리
- `voice_idle.py`: 음성 연결 유휴 시간 관리

### 기능별 Cog

- `cogs/leveling.py`: 채팅/음성 경험치, 랭킹 및 경험치 관리
- `cogs/titles.py`: 칭호 추가·삭제·목록·동기화
- `cogs/menu.py`: 식단 조회, 채널 설정, 자동 전송
- `cogs/traffic.py`: 교통정보 조회, 채널 설정, 주기적 알림
- `cogs/music.py`: 음악 검색·재생·대기열·대시보드·재생바
- `cogs/tts.py`: `/음성` 한국어 TTS 재생
- `cogs/help.py`: 도움말

### 데이터 조회

- `menu_source.py`: 대원여객 배차확인 Worker의 식단 API 호출
- `traffic_source.py`: 한국도로공사 고속도로 정체 API 호출 및 수도권 필터링
- `levels.py`: 경험치 계산 관련 공통 로직

### TTS

- `experimental/huggingface_korean_tts.py`: 실제 TTS 모델 로딩과 WAV 생성
- `experimental/requirements-tts.txt`: TTS 추가 의존성
- `experimental/README-TTS.md`: TTS 설치·시험 안내
- VPS 모델 경로: `/opt/honorary-bot/models/vits-mimic3-ko_KO-kss_low`

### 배포

- `deploy/honorary-bot.service`: systemd 서비스 예시
- `deploy/install.sh`: VPS 설치 보조 스크립트
- `requirements.txt`: 기본 Python 의존성
- `cloudflare/`: Cloudflare Worker 버전과 테스트. Discord 음성 재생 본체가 아님.

---

## 4. 환경변수와 영구 데이터

주요 환경변수:

```dotenv
DISCORD_TOKEN=
GUILD_ID=
DB_PATH=bot.db
BOT_OWNER_IDS=

MENU_HOUR_KST=6
ENABLE_MENU_TASK=1

HIGHWAY_API_KEY=
TRAFFIC_POLL_MINUTES=30
ENABLE_TRAFFIC_TASK=1

YTDLP_COOKIE_FILE=/opt/honorary-bot/youtube-cookies.txt
```

추가 레벨/음성 관련 변수는 `.env.example`과 `config.py`를 확인한다.

`BOT_OWNER_IDS`는 관리자 명령에 대한 명시적 소유자 예외 목록이며 쉼표로
구분한다. 비워 두거나 잘못 입력하면 예외 권한을 부여하지 않는다. 개인 Discord
ID는 코드나 문서에 기록하지 않고 VPS `.env`에서만 관리한다.

중요 사항:

- 실제 비밀값은 VPS `.env`에만 넣는다.
- YouTube 쿠키 파일은 저장소에 넣지 않는다.
- `DB_PATH`는 재시작 및 배포 후에도 보존되는 위치여야 한다.
- 서버별 식단/교통정보 채널은 `.env`가 아니라 `bot.db`에 저장된다.
- `.env`를 변경한 뒤에는 systemd 서비스를 재시작해야 새 설정이 반영된다.

---

## 5. 현재 구현된 Discord 명령어

최근 VPS 기동 시 서버 3곳에 총 30개 명령어가 동기화됐다.

### 레벨·칭호

- `/경험치`
- `/랭킹`
- `/경험치지급`
- `/경험치차감`
- `/경험치설정`
- `/칭호추가`
- `/칭호삭제`
- `/칭호목록`
- `/칭호동기화`

레벨 및 칭호 관리 명령은 관리자 전용으로 제한했다. 봇 소유자 예외는 `access_control.py`의 소유자 정책/환경변수에 따라 적용된다. 개인 Discord 사용자 ID는 문서에 기록하지 않는다. 단, 일반 조회 명령까지 전부 관리자 전용인지 여부는 각 데코레이터를 다시 확인한다.

### 식단

- `/식단`: 오늘 식단 즉시 조회
- `/식단채널설정`: 자동 전송 채널 설정
- `/식단채널해제`: 자동 전송 해제
- `/식단설정`: 현재 설정 확인

### 교통정보

- `/교통정보`: 현재 수도권 고속도로 심한 정체 구간 조회
- `/교통정보채널설정`
- `/교통정보채널해제`
- `/교통정보설정`
- `/교통정보주기설정`

### 음악

- `/재생 검색어`
- `/일시정지`
- `/재개`
- `/스킵`
- `/이동 초`
- `/정지`
- `/퇴장`
- `/대기열`
- `/볼륨 퍼센트`
- `/음악대시보드설정`

### TTS

- `/음성 내용 [목소리] [말투]`

### 기타

- `/도움말`

---

## 6. 음악 기능 구현 상태

### 완료된 동작

- YouTube URL 또는 가수명·노래 제목 검색
- Discord 음성채널 오디오 스트리밍
- 서버별 독립 대기열
- 재생, 일시정지, 재개, 스킵, 정지, 볼륨, 대기열, 위치 이동
- 봇이 음성 채널에 들어갈 때 자체 듣기(self-deaf) 활성화
- 음악 종료 후 즉시 퇴장하지 않고 음성 채널에 머무름
- `/퇴장`으로 명시적 퇴장
- 명령이나 재생이 10분 동안 없을 때 자동 퇴장
- 대시보드 버튼은 재시작 뒤에도 동작하는 persistent view
- `/음악대시보드설정` 실행 시 `회장님의-뮤직피아` 채널 생성 또는 재사용
- 대시보드 메시지 상단 고정
- 대시보드에서 곡명, 썸네일, 신청자, 재생 시간, 텍스트 재생바 표시
- 곡이 바뀌어도 새 메시지를 만들지 않고 같은 고정 대시보드 메시지를 수정
- 재생이 끝나면 같은 위치에 `현재 재생 중인 곡이 없습니다.` 표시
- 대시보드 버튼의 Command 객체 직접 호출 오류 수정
- 대시보드 채널의 일반 사용자 메시지는 5초 후 삭제
- `재생 목록에 추가` 및 `대기열에 추가` 안내는 10초 후 삭제
- 재시작 뒤 채널 캐시가 비어도 채널 이름과 고정 메시지로 대시보드 복원

### YouTube 관련 구성

- `yt-dlp`
- FFmpeg
- VPS IP 자동화 차단 대응용 선택적 쿠키 파일
- Deno 기반 YouTube EJS 검증 구성요소
- 스트림 URL은 만료될 수 있으므로 재생 직전에 다시 추출

주의: YouTube 쿠키는 만료되거나 계정 인증 상태가 바뀔 수 있다. 쿠키 오류 발생 시 브라우저에서 Netscape 형식으로 새로 내보내 VPS 파일을 교체하고 권한을 제한한다. 쿠키 내용을 채팅이나 GitHub에 붙이지 않는다.

### 최근 수정 커밋

- `bd357b5` — 현재 재생 정보를 고정 대시보드 내부에서 갱신
- `bc9d775` — 대시보드 버튼의 app command 호출 오류 수정
- `165da8f` — Deno 기반 YouTube EJS 검증 활성화
- `bd73234` — YouTube EJS 구성요소 설치
- `7514aaf` — VPS Deno 설치
- `5348eab` — YouTube 쿠키 파일 선택 지원
- `a970181` — 음악 재생 완료 콜백 경쟁 상태 수정
- `a2e0b3c` — VPS FFmpeg 설치 안내

---

## 7. TTS 구현 상태와 성능

### 기본 모델

- 엔진: Sherpa-ONNX
- 모델: `vits-mimic3-ko_KO-kss_low`
- 키: `fast_korean`
- 한국어 여성 음성
- 인터넷 API 없이 VPS 내부에서 생성
- `/음성`에서 목소리를 생략하면 반드시 이 모델을 사용

### 선택 가능한 음성

총 10개 선택지를 준비했다.

1. `fast_korean`: 빠른 한국어 VITS, 기본·추천
2. `sohee`
3. `vivian`
4. `serena`
5. `uncle_fu`
6. `dylan`
7. `eric`
8. `ryan`
9. `aiden`
10. `ono_anna`

2~10번은 Qwen3-TTS CustomVoice를 사용한다. GPU가 없는 현재 VPS에서는 모델 로드와 생성이 느리고 메모리를 약 5GB까지 사용할 수 있으므로 기본값으로 쓰지 않는다.

### 실제 VPS 성능 측정 결과

Sherpa-ONNX 기본 음성 기준:

| 입력 | 생성 음성 길이 | 최초 생성 | 모델 준비 후 |
|---|---:|---:|---:|
| 16자 | 약 2.4초 | 3.39초 | 0.13초 |
| 42자 | 약 6초 | 0.52초 | 0.24초 |
| 106자 | 약 13초 | 0.69초 | 0.79초 |

- 봇 재시작 후 첫 호출은 모델 로딩 때문에 약 3~4초
- 이후 일반 문장은 대체로 0.1~0.8초
- Discord 음성 연결까지 포함하면 보통 1~3초 후 재생
- Qwen 음성을 선택하면 CPU VPS에서 약 20~60초 걸릴 수 있음

### 음성 연결 정책

- TTS 후 자동 퇴장하지 않음
- 한 번 입장한 채널에 유지
- 별도 `/퇴장` 명령으로 퇴장
- 10분 동안 아무 명령·재생이 없을 때만 자동 퇴장
- 음성채널 입장 시 봇의 듣기는 꺼짐(self-deaf)

관련 커밋:

- `4a926df` — 한국어 TTS 음성 재생 추가
- `52b0229` — 빠른 한국어 ONNX TTS를 기본으로 변경
- `9624269` — 음성 연결을 유지하고 유휴 시에만 퇴장

---

## 8. 식단 기능 현재 상태

식단 데이터 소스:

```text
https://daewon-dispatch.kcy990830.workers.dev
POST JSON: {"action":"foodmenu"}
```

2026-09-11 VPS 직접 조회 시험에서는 조식·중식·석식 데이터가 정상 반환됐다. 따라서 데이터 조회 코드는 현재 정상이다.

현재 자동 전송이 되지 않는 이유:

- `bot.db`의 `guild_settings`가 비어 있음
- 각 Discord 서버에서 식단 전송 채널을 지정하지 않음
- 로그에 `식단을 보낼 채널이 지정되지 않았습니다. (/식단채널설정)` 기록

복구 방법:

1. 각 서버에서 원하는 채널로 이동
2. `/식단채널설정` 실행
3. `/식단설정`으로 상태 확인
4. `/식단`으로 즉시 조회 시험

현재 자동 전송 시각은 `.env` 기준 매일 오전 6시(KST)다.

주의: 배포 중 `bot.db`를 덮어쓰면 서버별 채널 설정이 다시 사라진다.

---

## 9. 교통정보 기능 현재 상태

데이터 소스: 한국도로공사 Open API `trafficAmountByCongest`

현재 작동하지 않는 직접 원인:

- VPS `/opt/honorary-bot/.env`의 `HIGHWAY_API_KEY` 값이 비어 있음
- 서버별 교통정보 전송 채널도 `bot.db`에 지정되지 않음
- 자동 작업 플래그 자체는 `ENABLE_TRAFFIC_TASK=1`
- 확인 주기는 `TRAFFIC_POLL_MINUTES=30`

복구 방법:

1. 한국도로공사에서 발급받은 키를 VPS `.env`의 `HIGHWAY_API_KEY=` 뒤에 입력
2. 봇 서비스 재시작
3. 각 Discord 서버에서 `/교통정보채널설정` 실행
4. `/교통정보설정`으로 상태 확인
5. `/교통정보`로 즉시 조회 시험

API 키는 이 문서나 GitHub에 추가하지 않는다.

---

## 10. 권한 정책

사용자가 요청한 정책:

- 레벨, 칭호, 유저관리, 채팅관리 명령은 관리자만 사용
- 봇 소유자 예외는 `access_control.py`의 소유자 정책/환경변수에 따라 적용

현재 명확히 구현된 범위:

- 레벨 관리 및 칭호 관리 명령에 관리자 제한과 소유자 우회 적용
- 공통 로직은 `access_control.py`
- 관련 커밋: `bd8dd83`

확인 또는 추가 구현이 필요한 범위:

- 별도의 유저관리/채팅관리 Cog가 실제로 존재하는지 확인
- 새 관리 명령을 추가할 때 동일한 공통 권한 검사를 빠뜨리지 않기
- 조회 명령과 변경 명령 중 어느 범위까지 관리자 전용으로 할지 사용자 의도 재확인

---

## 11. Discord에서 구현할 수 없는 요청

사용자는 음성채널 사용자 목록에서 봇을 항상 최상단 또는 최하단에 배치하고 싶어 했다.

Discord의 음성채널 멤버 표시 순서는 봇 코드가 직접 지정할 수 없다. 역할 순서, 닉네임, 클라이언트 표시 방식 등에 따라 달라질 수 있으며 API에서 멤버 UI 정렬 위치를 고정하는 기능은 제공하지 않는다. 역할을 별도로 만들고 역할 순서를 조정하는 정도만 시도할 수 있지만 정확한 위치는 보장할 수 없다.

---

## 12. 배포 및 운영 절차

아래 명령은 절차 참고용이다. 원격 push와 VPS/운영 배포는 각각 사용자의 명시적 승인을 받은 뒤에만 실행한다. 커밋·QA·push·배포는 서로 독립된 상태이며, 하나의 승인이나 완료를 다른 단계의 승인으로 확대 해석하지 않는다.

### 코드 검증

Python 문법 검사 예시:

```bash
python -m py_compile bot.py cogs/*.py
```

관련 기능별 추가 시험을 수행한다. 로컬 PC에 일부 TTS/yt-dlp 패키지가 없을 수 있으므로 최종 검증은 VPS 가상환경에서도 한다.

### VPS 반영

사용자가 해당 커밋의 배포를 명시적으로 승인한 경우에만 진행한다. 운영 디렉터리는 `/opt/honorary-bot`이다. 보호 대상 백업과 제외 설정을 확인하고 변경 파일을 반영한 다음:

```bash
cd /opt/honorary-bot
.venv/bin/python -m py_compile bot.py cogs/*.py
sudo systemctl restart honorary-bot
sudo systemctl is-active honorary-bot
sudo journalctl -u honorary-bot -n 100 --no-pager
```

`active` 상태와 다음 항목을 확인한다.

- 모든 Cog 로드 완료
- Discord Gateway 연결 완료
- 서버별 슬래시 명령어 동기화 완료
- 새 traceback 없음

### GitHub 반영

```bash
git status
git diff --check
git add <변경 파일>
git commit -m "변경 내용을 설명하는 메시지"
# 작업 브랜치 push를 사용자가 명시적으로 승인한 경우에만 실행
git push -u origin HEAD

# 공식 기준 브랜치 반영은 대상 브랜치 push를 별도로 명시 승인받고,
# 독립 QA 및 원격 최신 상태 확인 후에만 실행 (일반 push이므로 non-fast-forward는 거부됨)
git fetch origin claude/how-it-works-x3928d
git push origin HEAD:refs/heads/claude/how-it-works-x3928d
```

당분간 공식 기준인 `claude/how-it-works-x3928d`를 유지한다. 작업 브랜치 push 승인과 공식 기준 브랜치 push 승인은 서로 다르며, `HEAD:<공식 브랜치>` 반영은 사용자가 대상 브랜치를 명시한 경우에만 수행한다. `main`은 레거시이며, 검증된 통합과 사용자의 명시적 전환 승인 전에는 공식 기준으로 바꾸지 않는다. 현재 저장소에는 VPS 자동 배포 workflow가 없고 Cloudflare 배포 workflow만 공식 기준 브랜치의 `cloudflare/**` 변경을 감시하므로, push와 각 배포 영향은 실행 전에 따로 확인한다.

### 자동 배포 권장 방식

- 사용자가 자동 배포 구성과 실행을 명시적으로 승인한 경우에만 설정
- GitHub Actions에서 사용자가 승인한 브랜치 push 감지
- SSH 키는 GitHub Actions Secrets에 저장
- 서버에서 `git pull` 또는 검증된 배포 아카이브 반영
- `.env`, `bot.db`, `youtube-cookies.txt`, TTS 모델 디렉터리는 배포 대상에서 제외
- 문법 검사 성공 후에만 서비스 재시작
- 실패 시 기존 프로세스 유지 또는 이전 릴리스로 복구

---

## 13. Git 변경 이력 요약

최근 핵심 커밋:

```text
bd357b5 fix: keep now playing inside pinned dashboard
bc9d775 fix: invoke music commands from dashboard controls
52b0229 perf: use fast Korean ONNX TTS by default
bd8dd83 feat: restrict level and title commands to administrators
9624269 feat: keep voice connection until idle or leave command
4a926df feat: add Korean TTS voice playback
165da8f fix: Deno 기반 유튜브 EJS 검증 활성화
bd73234 fix: 유튜브 EJS 검증 구성요소 설치
7514aaf fix: VPS 유튜브 검증용 Deno 설치
5348eab fix: 유튜브 차단 대응용 선택 쿠키 파일 지원
77e33dc fix: 긴 도움말을 임베드 제한에 맞게 분할
a970181 fix: 음악 재생 완료 콜백 경쟁 상태 방지
015c747 docs: 음악 재생 명령어와 VPS 설정 안내 추가
a2e0b3c feat: VPS 음악 재생용 FFmpeg 설치
```

---

## 14. 사용자 요구사항과 대화 흐름 요약

1. 사용자가 GitHub 명예회장봇 프로젝트를 기준으로 기존 기능을 정확히 파악해 달라고 요청했다.
2. Cloudflare와 GitHub 자동 배포를 원했지만, 음악 재생 목적 때문에 실제 봇은 Hostinger VPS에서 운영하는 방향으로 정리했다.
3. YouTube URL 또는 검색어로 음성채널에서 음악을 듣는 기능을 추가했다.
4. YouTube가 VPS 요청을 봇으로 판단해 차단하면서 쿠키 파일과 Deno/EJS 검증을 적용했다.
5. 오리뮤직과 유사한 Discord 음악 대시보드를 원했지만, 이미지는 명예회장봇 전용 로봇 이미지로 교체했다.
6. 대시보드 자동 채널 생성, 버튼, 도움말, 썸네일, 재생 시간과 이동 기능을 추가했다.
7. 대시보드 버튼에서 `Command object is not callable` 오류가 발생해 `.callback(...)` 방식으로 수정했다.
8. 현재 재생 메시지가 곡마다 생성되지 않고 고정 대시보드 하단에서 변경되도록 수정했다.
9. 재생 목록 추가 안내는 10초 후 삭제하고 일반 채팅은 5초 후 삭제하도록 설정했다.
10. 한국어 `/음성` TTS 기능을 추가했고, 기본 모델을 빠른 Sherpa-ONNX VITS로 정했다.
11. 고품질 Qwen 음성 9개도 선택 가능하게 했지만 CPU VPS에서 느리므로 기본으로 쓰지 않는다.
12. TTS 후 봇이 계속 음성채널에 머무르고, 10분간 유휴 상태이거나 `/퇴장` 실행 시에만 나가도록 했다.
13. 봇 음성 연결 시 듣기 상태를 껐다.
14. 레벨·칭호 관리 명령은 관리자 전용으로 제한하고 `access_control.py`의 소유자 정책/환경변수에 따른 예외를 적용했다.
15. 식단과 교통정보가 작동하지 않는 문제를 점검한 결과 식단 채널 미설정, 교통 API 키 및 채널 미설정이 원인이었다.
16. Codex Cloud와 GitHub 환경 연결 방법을 안내했지만 실제 Discord 봇 실행 환경은 VPS에 유지하기로 했다.

---

## 15. 확인이 필요한 문제와 다음 우선순위

### 즉시 처리

1. 각 서버에서 `/식단채널설정` 실행
2. VPS `.env`에 `HIGHWAY_API_KEY` 등록
3. 서비스 재시작
4. 각 서버에서 `/교통정보채널설정` 실행
5. `bot.db`가 자동 배포에서 제외되는지 확인

### 기능 검증

1. 대시보드에서 두 곡 연속 추가
2. 현재 곡 정보가 같은 고정 메시지에서 변경되는지 확인
3. 추가 안내가 10초 후 삭제되는지 확인
4. 일반 채팅이 5초 후 삭제되는지 확인
5. `/이동`, 일시정지, 재개, 스킵, 정지 버튼 확인
6. `/음성`에서 목소리를 생략했을 때 Sherpa-ONNX가 사용되는지 로그로 확인
7. 음악/TTS 종료 후 10분 유휴 퇴장 확인

### 운영 개선

1. 사용자 명시적 승인 후 GitHub → VPS 자동 배포 구성
2. 배포 전 백업 및 롤백 절차 추가
3. `.env`, DB, 쿠키, 모델 디렉터리 보호
4. 식단/교통정보 설정 누락을 시작 로그에서 더 분명하게 표시
5. 봇 상태 점검용 간단한 `/상태` 명령 고려
6. Qwen 음성은 생성 중 안내를 즉시 표시하고 예상 대기시간 제공

---

## 16. 새 에이전트에게 전달할 시작 프롬프트

아래 내용을 Hermes Agent의 새 작업 시작 메시지로 사용하면 된다.

```text
명예회장봇 프로젝트를 이어서 관리해 주세요. 먼저 첨부한 `명예회장봇-Hermes-Agent-인수인계.md`를 끝까지 읽고, 저장소의 README.md, .env.example, config.py, db.py 및 관련 Cog를 확인하세요.

GitHub 저장소는 https://github.com/Kimmacaroni/myhjbb-.git 이고 당분간 공식 기준 브랜치는 claude/how-it-works-x3928d 입니다. main은 레거시이므로 검증된 통합과 사용자의 명시적 승인 전에는 공식 기준으로 전환하지 마세요. 로컬이나 VPS에 기존 변경이 있으면 절대 덮어쓰지 마세요. 실제 봇은 Hostinger VPS의 /opt/honorary-bot에서 systemd 서비스 honorary-bot으로 실행됩니다.

Discord 토큰, API 키, YouTube 쿠키, SSH 키와 비밀번호를 출력하거나 GitHub에 커밋하지 마세요. .env, bot.db, youtube-cookies.txt, models 디렉터리는 배포 시 보존해야 합니다.

현재 최우선 과제는 식단/교통정보 설정 복구와 설정 데이터 보존 확인입니다. 먼저 로컬 상태를 진단하고 수정 후 로컬 검증과 커밋까지 수행하세요. GitHub push와 VPS 접속·서비스 조작·배포는 각각 사용자의 명시적 승인을 받은 뒤에만 실행하세요. 승인된 배포 후에는 서비스 활성 상태, 최근 로그, Discord 명령 동기화를 확인하세요. 구현/독립 QA/push/배포의 완료·미완료·사용자 입력 필요 사항을 각각 구분해 보고해 주세요.
```

---

## 17. 자료 전달 체크리스트

Hermes Agent에 전달할 수 있는 자료:

- 이 인수인계 Markdown 파일
- GitHub 저장소 주소
- 작업 브랜치 이름
- 필요한 경우 오류 화면 캡처
- 비밀값을 제거한 로그

채팅으로 전달하면 안 되는 자료:

- Discord 봇 토큰
- 한국도로공사 API 키 원문
- YouTube cookies.txt 내용
- VPS root 비밀번호
- SSH 개인키
- `.env` 전체 내용
- 사용자 개인정보가 포함된 DB 원본

비밀값이 꼭 필요하면 사용자가 직접 VPS나 Hermes의 안전한 Secret/Environment 설정 화면에 입력해야 한다.

---

## 18. 문서 한계

이 문서는 현재 대화에서 확인 가능한 요청과 실제 코드·VPS 점검 결과를 토대로 작성한 기술 인수인계 요약이다. 서비스의 전체 원본 대화 내보내기 파일은 아니며, 메시지별 전문 대신 새 에이전트가 작업을 이어가는 데 필요한 결정, 구현 내용, 오류, 운영 방법과 남은 과제를 구조화했다. 최종 사실 확인은 저장소 코드, Git 기록, VPS 상태와 Discord 실제 동작을 기준으로 한다.


