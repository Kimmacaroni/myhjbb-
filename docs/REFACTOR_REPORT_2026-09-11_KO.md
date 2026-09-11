# 명예회장봇 VPS 기능별 코드 정리 보고서

- **상태**: 구현 완료 / 독립 QA 승인 / PR 검토 중 / VPS 배포 미수행
- **기능 정리 커밋**: `ad3e2f0d60c1b2d8b7cac63f4525aead8c45a933`
- **Pull Request**: <https://github.com/Kimmacaroni/myhjbb-/pull/3>
- **기준 브랜치**: `claude/how-it-works-x3928d`
- **구현 부서**: 명예회장봇 코드 정리 담당
- **검토 부서**: 독립 QA·보안 검토부

## 변경 내용

- VPS Cog 7개와 Discord 슬래시 명령 30개 보존
- 참조가 없는 `Music._progress_embed` 제거
- 음악 시간·재생바 계산을 `music_helpers.py` 순수 헬퍼로 분리
- 음악·TTS의 Discord 재생 완료 콜백을 `voice_playback.py`로 통합
- Discord 개인 사용자 ID 하드코딩 제거
- `BOT_OWNER_IDS` 환경변수와 fail-closed 파서 추가
- VPS 기능 소유권·Cloudflare 보조 범위·영구 데이터를 `docs/FEATURE_MAP.md`에 정리
- 구조 검증 도구 추가

## 보존한 코드

Cloudflare 구현은 VPS 음성 봇 본체가 아니라 보조 기능이므로 삭제하지 않았습니다. 음악·TTS·식단·교통정보·경험치·칭호 기능도 모두 보존했습니다.

## 검증

- Python 단위 테스트 9/9 통과
- Python 전체 `compileall` 통과
- 구조 검사 통과: Cog 7개·명령 30개
- Cloudflare 기존 `npm test` 전체 통과
- 음악/TTS 완료 콜백 및 진행바 헬퍼 테스트 통과
- 개인 ID·시크릿·개인 절대경로 미검출
- 독립 QA에서 확인된 기능 회귀 및 P1 없음

## 배포 전 필수 조건

- VPS `.env`에 `BOT_OWNER_IDS` 설정 여부 확인
- 과거 Discord 토큰의 폐기·재발급 완료 여부 확인
- `bot.db`, `.env`, YouTube 쿠키, TTS 모델 백업·보존
- 사용자 명시적 배포 지시 후에만 VPS 반영
