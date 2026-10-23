#!/usr/bin/env bash
# Apply only the reviewed Python changes; preserve all operational data.
set -Eeuo pipefail
source_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
app_dir=/opt/honorary-bot
declare -A baseline=(
  [bot.py]=6d6eb4a70db75907f0f11305687818cdee674bfe9aca4dd08da96c42763c487c
  [access_control.py]=f098b4b3830c11bbe06b46a5e95ff37e3360c1952b621db269ccaae1d7c6796a
  [cogs/music.py]=497084b456ad6decdf1390bee93f3623a0833fc07bd2a6d6c2d7dcb3dfd9346c
)
for relative in "${!baseline[@]}"; do
  actual_sha="$(sha256sum "$app_dir/$relative" | cut -d ' ' -f 1)"
  [[ "$actual_sha" == "${baseline[$relative]}" ]] || {
    echo "운영 $relative 파일이 기준과 달라 중단했습니다." >&2; exit 1;
  }
done
for relative in music_matching.py cogs/announcements.py; do
  [[ ! -e "$app_dir/$relative" ]] || {
    echo "운영 $relative 파일이 이미 있어 덮어쓰지 않습니다." >&2; exit 1;
  }
done
"$app_dir/.venv/bin/python" - "$source_dir" <<'PY'
import sys
from pathlib import Path
import discord
import davey
import yt_dlp
assert tuple(map(int, discord.__version__.split('.')[:3])) >= (2, 7, 1)
for name in ('bot.py', 'access_control.py', 'cogs/music.py',
             'music_matching.py', 'cogs/announcements.py'):
    path = Path(sys.argv[1]) / name
    compile(path.read_text(), str(path), 'exec')
print('운영 파일 기준·Python 의존성·문법 검사 통과')
PY
if [[ "${1:-}" == --check ]]; then exit 0; fi
if [[ $EUID -ne 0 ]]; then
  echo '배포에는 root 권한이 필요합니다. sudo bash로 실행하세요.' >&2
  exit 1
fi
backup_dir="$(mktemp -d "$app_dir/music-notice-backup-XXXXXXXX")"
for relative in bot.py access_control.py cogs/music.py requirements.txt; do
  mkdir -p "$backup_dir/$(dirname "$relative")"
  cp -p "$app_dir/$relative" "$backup_dir/$relative"
done
rollback() {
  trap - ERR
  for relative in bot.py access_control.py cogs/music.py requirements.txt; do
    cp -p "$backup_dir/$relative" "$app_dir/$relative"
  done
  rm -f "$app_dir/music_matching.py" "$app_dir/cogs/announcements.py"
  systemctl restart honorary-bot.service || true
  echo "배포 실패: 원본 복구. 백업: $backup_dir" >&2
}
trap rollback ERR
install -m 644 "$source_dir/music_matching.py" "$app_dir/music_matching.py"
install -m 644 "$source_dir/cogs/announcements.py" "$app_dir/cogs/announcements.py"
for relative in bot.py access_control.py cogs/music.py requirements.txt; do
  cat "$source_dir/$relative" > "$app_dir/$relative"
done
started_at="$(date --iso-8601=seconds)"
systemctl restart honorary-bot.service
ready=false
for attempt in {1..20}; do
  sleep 2
  if ! systemctl is-active --quiet honorary-bot.service; then
    echo '서비스 시작 실패' >&2
    false
  fi
  startup_log="$(journalctl -u honorary-bot.service --since "$started_at" --no-pager -o cat)"
  if [[ "$startup_log" == *'cogs.announcements 로드 완료'* &&
        "$startup_log" == *'공지임베드'* && "$startup_log" == *'공지텍스트'* ]]; then
    ready=true
    break
  fi
done
[[ "$ready" == true ]] || { echo '공지 명령 등록 확인 실패' >&2; false; }
trap - ERR
echo "음악 수정·공지 기능 배포 및 명령 등록 확인 완료. 백업: $backup_dir"
echo '실제 음악 소리와 공지 게시 여부는 Discord에서 확인해야 합니다.'
