# 명예회장봇 작업 기록

이 문서는 저장소 변경의 시작·완료·검증·인수인계 이력을 시간순으로 보존한다. 기록 방법과 필수 안전 수칙은 루트 [`AGENTS.md`](../AGENTS.md)를 따른다. 최신 항목을 위에 추가하며, 기존 항목은 삭제하거나 결과를 소급해 바꾸지 않는다(오류 정정은 정정 기록으로 남긴다).

## 상태 표기

- `구현 진행 중` / `구현 완료`: 구현 및 구현자 자체 검증 상태
- `QA 대기` / `QA 완료` / `QA 거부`: 구현자와 분리된 독립 QA 상태
- `push 미승인` / `push 승인` / `push 완료`: 원격 반영 상태
- `배포 미승인` / `배포 승인` / `배포 완료`: 운영 반영 상태
- `보류` / `실패`: 원인 및 재개 조건을 기록함

각 상태는 독립적이다. 구현 완료가 독립 QA 완료를 뜻하지 않고, 독립 QA 완료도 push 또는 배포 승인·완료를 뜻하지 않는다. 기록은 엄격한 append-only로 관리하여 기존 항목을 삭제·수정·재정렬하지 않고 정정은 새 블록으로 추가한다. 단, 비밀값·개인정보·개인 절대 경로가 이미 기록된 경우에는 값 자체를 중립 표기로 치환하고 새 보안 정정 블록에 치환 사실을 남긴다.

---

## 2026-09-11 — 인수인계 문서 QA 거부 사유 보완

### 시작 기록

- 상태: 구현 진행 중 / QA 대기 / push 미승인 / 배포 미승인
- 시작: 2026-09-11 20:40 KST
- 목적: QA에서 거부된 개인 경로·개인 Discord ID 노출, 승인 없는 push·배포 절차, 상태 및 기록 규칙의 모호성 보완
- 구현자: Hermes Agent (haruworks)
- QA 검토자: 미지정 — 수정 완료 후 독립 QA 필요
- 브랜치: `haruworks/vps-migration` (`claude/how-it-works-x3928d` 기반)
- worktree: `$WORKTREE`
- 기준 SHA: `19566983d4aedd23b3c9e23a9c0f68a78bc853d0`
- 대상 파일: `AGENTS.md`, `README.md`, `cloudflare/README.md`, `docs/HERMES_AGENT_HANDOFF_KO.md`, `docs/WORK_LOG.md`
- 계획 검증: `git diff --check`, 개인 절대 경로·Discord 개인 ID·비밀값 패턴 검사, staged diff 확인
- 보안 정정: 기존 작업 기록의 개인 실행환경 절대 경로를 `$WORKTREE`로 치환하고, 인수인계 문서의 개인 Windows 절대 경로와 Discord 개인 사용자 ID를 제거한다. 이는 append-only 원칙의 보안 예외이며 본 블록으로 변경 사실을 보존한다.
- push: 사용자 명시적 승인이 없으므로 금지
- 배포: 사용자 명시적 승인이 없으므로 금지

### 완료 기록

- 상태: 구현 완료 / QA 대기 / push 미승인 / 배포 미승인
- 완료: 2026-09-11 20:44 KST
- 변경 파일: `AGENTS.md`, `README.md`, `cloudflare/README.md`, `docs/HERMES_AGENT_HANDOFF_KO.md`, `docs/WORK_LOG.md`
- 결과: 개인 Windows 절대 경로와 Discord 개인 사용자 ID를 제거하고, 기존 작업 기록의 개인 실행환경 경로를 `$WORKTREE`로 치환함
- 결과: 모든 문서의 원격 push·배포 절차를 사용자 명시적 승인 후로 통일하고, 공식 기준 브랜치와 레거시 `main` 전환 조건을 명시함
- 결과: 엄격한 append-only 규칙과 구현/독립 QA/push/배포 상태 분리를 명시함
- 검증: `git diff --check` 성공
- 검증: 추적 중인 Markdown 6개에서 Windows 절대 경로, 개인 실행환경 절대 경로, 17~20자리 Discord ID, 개인키 헤더, 실제 값이 채워진 주요 secret 할당 패턴 없음
- 커밋 SHA: 본 기록을 포함하는 작업 커밋 (`git log -1 --format=%H`로 확인)
- 독립 QA: 미수행 — 구현자와 다른 검토자의 확인 필요
- push: 수행하지 않음 (사용자 명시적 승인 없음)
- 배포: 수행하지 않음 (사용자 명시적 승인 없음)

---

## 2026-09-11 — GitHub 작업 기록 표준 도입

### 시작 기록

- 상태: 진행 중
- 시작: 2026-09-11 20:27 KST
- 목적: 명예회장봇의 GitHub 인수인계 및 작업 기록 표준을 저장소에 명문화
- 구현자: Hermes Agent (haruworks)
- QA 검토자: 미지정 — 독립 QA 대기
- 브랜치: `haruworks/vps-migration`
- worktree: `$WORKTREE`
- 기준 SHA: `f3c429732ba0500354a17afab990dbd15f459b02`
- 계획 파일: `AGENTS.md`, `docs/WORK_LOG.md`, `docs/HERMES_AGENT_HANDOFF_KO.md`, `.gitignore`
- 계획 검증: `git diff --check`, 전체 추적 대상 Python 문법 검사, staged diff 확인
- 배포: 사용자 명시 지시가 없으므로 금지
- push: 요청되지 않았으므로 금지

### 완료 기록

- 상태: QA 대기 (구현 및 자체 검증 완료, 독립 QA 미수행)
- 완료: 2026-09-11 20:28 KST
- 변경 파일: `AGENTS.md`, `docs/WORK_LOG.md`, `docs/HERMES_AGENT_HANDOFF_KO.md`, `.gitignore`
- 결과: 브랜치/worktree 격리, 시작·완료 기록, 민감정보 및 영구 데이터 보호, 배포 승인·백업·문법 검사·systemd 로그 검증, 구현/QA 분리, 한국어 보고 규칙을 도입함
- 검증: `git diff --check` 성공
- 검증: `python3 -m compileall -q -x '(^|/)(\.git|\.venv|venv|models)(/|$)' .` 성공
- 커밋 SHA: 본 기록을 포함하는 작업 커밋 (`git log -1 --format=%H`로 확인)
- 배포: 수행하지 않음 (사용자 명시 지시 없음)
- push: 수행하지 않음 (요청 없음)
- 후속 작업: 병합 또는 배포 전에 구현자와 다른 QA 검토자가 변경 diff와 안전 규칙을 독립 확인

---

## 2026-09-11 — VPS 기능 보존 코드 정리

### 시작 기록

- 상태: 구현 진행 중 / QA 대기 / push 미승인 / 배포 미승인
- 시작: 2026-09-11 20:58 KST
- 목적: 공식 운영 진입점 `bot.py`와 기능별 Cog를 보존하면서 참조·등록·테스트 근거에 따라 복잡도, 더미, 중복을 안전하게 축소하고 구조 검증을 추가
- 구현자: Hermes Agent (haruworks)
- QA 검토자: 미지정 — 구현 완료 후 독립 QA 필요
- 브랜치: `refactor/vps-feature-cleanup`
- worktree: `$WORKTREE`
- 기준 SHA: `e93ae85b9a738e94ea702284237c57a8549431bf`
- 대상 파일: VPS Python 구현(특히 `cogs/music.py`, TTS/voice helper), Python 테스트, `docs/FEATURE_MAP.md`, `scripts/verify_structure.py`, `docs/WORK_LOG.md`
- 계획 검증: import·명령 등록·참조 분석, Python 신규 테스트, 구조 검증, 전체 `compileall`, `cloudflare/`의 `npm test`, `git diff --check`, staged diff 확인
- 보존 범위: `cloudflare/` 보조 구현, `bot.py`의 Cog 로드 경로, `.env`, `bot.db`, 쿠키, `models/` 및 모든 영구 데이터
- push: 사용자 명시적 승인이 없으므로 금지
- 배포: 사용자 명시적 승인이 없으므로 금지

### 기록 순서 정책 정정

- 이 파일 3행의 `최신 항목을 위에 추가` 안내는 엄격한 append-only 규칙과 충돌하는 과거 문구이므로 더 이상 적용하지 않는다.
- 기존 문구 자체는 이력 보존을 위해 수정·삭제하지 않으며, 이 기록부터 모든 새 시작·완료·정정 블록은 **파일 끝에만 추가**한다.

### 완료 기록

- 상태: 구현 완료 / QA 대기 / push 미승인 / 배포 미승인
- 완료: 2026-09-11 21:06 KST
- 변경 파일: `.env.example`, `README.md`, `access_control.py`, `owner_ids.py`, `cogs/music.py`, `music_helpers.py`, `cogs/tts.py`, `voice_playback.py`, `tests/`, `scripts/verify_structure.py`, `docs/FEATURE_MAP.md`, `docs/HERMES_AGENT_HANDOFF_KO.md`, `docs/WORK_LOG.md`
- 정리 근거: 저장소 전체 참조 검색에서 0건이던 `Music._progress_embed`만 삭제했고, 실제 대시보드에서 중복 계산하던 시간/재생바 형식은 테스트 가능한 `music_helpers.py`로 추출함
- 중복 축소: 음악과 TTS에 각각 있던 Discord `after` 콜백→Future 연결을 `voice_playback.py`로 통합하고, 음악은 기존처럼 대시보드 갱신 전에 재생을 시작하도록 회귀 테스트함
- 접근 제어: 개인 Discord ID 하드코딩을 제거하고 `BOT_OWNER_IDS` 환경변수 기반 집합으로 교체함. 미설정·오타·음수·범위 초과는 예외 권한을 부여하지 않으며 파싱 테스트를 추가함
- 보존 근거: `bot.py`의 VPS Cog 7개와 슬래시 명령 30개를 구조 검사로 고정했고 `cloudflare/` 핵심 구현·테스트를 보존함. 참조가 없더라도 운영·호환성 검증이 없는 레거시 TTS 경로와 독립 식단 파일은 삭제하지 않음
- 문서: VPS 기능별 소유권, Cloudflare 보조 경계, 영구 데이터, 검증 명령을 `docs/FEATURE_MAP.md`에 기록함. 실제 workflow 2개와 VPS 자동 배포 workflow 부재, 공식 브랜치 별도 push 승인 절차, 과거 평문 토큰 폐기·재발급 `확인 필요` 상태를 명시함
- 검증: `python3 -m unittest discover -s tests -v` — 9개 성공
- 검증: `python3 scripts/verify_structure.py` — VPS Cog 7개, 슬래시 명령 30개, Cloudflare 보조 범위 보존 확인
- 검증: `python3 -m compileall -q -x '(^|/)(\.git|\.venv|venv|models)(/|$)' .` — 성공
- 검증: `(cd cloudflare && npm test)` — 전체 성공
- 검증: `git diff --check` — 성공
- 커밋 SHA: 본 기록을 포함하는 작업 커밋 (`git log -1 --format=%H`로 확인)
- 독립 QA: 미수행 — 구현자와 다른 검토자의 확인 필요
- 운영 주의: 기존 하드코딩 소유자 예외가 필요하면 배포 전 VPS `.env`에 `BOT_OWNER_IDS`를 안전하게 설정해야 함
- 토큰 상태: 과거 평문 토큰의 폐기·재발급은 저장소에서 확인할 수 없어 완료로 기록하지 않음 — 운영자 확인 필요
- push: 수행하지 않음 (사용자 명시적 승인 없음)
- 배포: 수행하지 않음 (사용자 명시적 승인 없음)
