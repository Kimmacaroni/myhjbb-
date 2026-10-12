#!/usr/bin/env bash
set -Eeuo pipefail
source_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
app_dir=/opt/honorary-bot
expected_sha=99ce5a9813a538c87484a747c4b6202ae409afa8158a7bd80f4f97bfa9c5603c
[[ "$(sha256sum "$app_dir/cogs/music.py" | cut -d ' ' -f 1)" == "$expected_sha" ]] || {
  echo '운영 음악 코드가 기준과 달라 중단했습니다.' >&2; exit 1;
}
[[ ! -e "$app_dir/music_queue.py" ]] || {
  echo '기존 music_queue.py를 덮어쓰지 않습니다.' >&2; exit 1;
}
"$app_dir/.venv/bin/python" - "$source_dir" <<'PY'
import sys
from pathlib import Path
for name in ('cogs/music.py', 'music_queue.py'):
    path = Path(sys.argv[1]) / name
    compile(path.read_text(), str(path), 'exec')
print('배포 기준 및 문법 검사 통과')
PY
if [[ "${1:-}" == --check ]]; then exit 0; fi
[[ $EUID -eq 0 ]] || { echo 'root 권한이 필요합니다.' >&2; exit 1; }
backup_dir="$(mktemp -d "$app_dir/queue-backup-XXXXXXXX")"
cp -p "$app_dir/cogs/music.py" "$backup_dir/music.py"
rollback() {
  trap - ERR
  cp -p "$backup_dir/music.py" "$app_dir/cogs/music.py"
  rm -f "$app_dir/music_queue.py"
  systemctl restart honorary-bot.service || true
  echo "배포 실패: 원본 복구. 백업: $backup_dir" >&2
}
trap rollback ERR
install -m 644 "$source_dir/music_queue.py" "$app_dir/music_queue.py"
cat "$source_dir/cogs/music.py" > "$app_dir/cogs/music.py"
started_at="$(date --iso-8601=seconds)"
systemctl restart honorary-bot.service
ready=false
for attempt in {1..20}; do
  sleep 2
  systemctl is-active --quiet honorary-bot.service
  startup_log="$(journalctl -u honorary-bot.service --since "$started_at" --no-pager -o cat)"
  if [[ "$startup_log" == *'cogs.music 로드 완료'* && "$startup_log" == *'로그인 완료'* ]]; then
    ready=true
    break
  fi
done
[[ "$ready" == true ]] || { echo '음악 Cog 및 로그인 확인 실패' >&2; false; }
trap - ERR
echo "대기열 표시 수정 배포 완료. 백업: $backup_dir"
