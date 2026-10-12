#!/usr/bin/env bash
# Targeted deployment; does not touch credentials, database, cookies, or models.
set -Eeuo pipefail
if [[ $EUID -ne 0 ]]; then
  echo 'root 권한으로 실행해야 합니다.' >&2
  exit 1
fi
source_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
app_dir=/opt/honorary-bot
expected_sha=497084b456ad6decdf1390bee93f3623a0833fc07bd2a6d6c2d7dcb3dfd9346c
actual_sha="$(sha256sum "$app_dir/cogs/music.py" | cut -d ' ' -f 1)"
[[ "$actual_sha" == "$expected_sha" ]] || {
  echo '운영 음악 코드가 기준 버전과 달라 배포를 중단했습니다.' >&2; exit 1;
}
[[ ! -e "$app_dir/music_matching.py" ]] || {
  echo '기존 music_matching.py가 있어 덮어쓰지 않습니다.' >&2; exit 1;
}
"$app_dir/.venv/bin/python" - "$source_dir" <<'PY'
import sys
from pathlib import Path
import discord
import davey
import yt_dlp
assert tuple(map(int, discord.__version__.split('.')[:3])) >= (2, 7, 1)
for name in ('cogs/music.py', 'music_matching.py'):
    path = Path(sys.argv[1]) / name
    compile(path.read_text(), str(path), 'exec')
PY
backup_dir="$(mktemp -d "$app_dir/music-backup-XXXXXXXX")"
cp -p "$app_dir/cogs/music.py" "$backup_dir/music.py"
cp -p "$app_dir/requirements.txt" "$backup_dir/requirements.txt"
rollback() {
  cp -p "$backup_dir/music.py" "$app_dir/cogs/music.py"
  cp -p "$backup_dir/requirements.txt" "$app_dir/requirements.txt"
  rm -f "$app_dir/music_matching.py"
  systemctl restart honorary-bot.service || true
  echo "배포 실패: 기존 파일로 복구했습니다. 백업: $backup_dir" >&2
}
trap rollback ERR
install -m 644 "$source_dir/music_matching.py" "$app_dir/music_matching.py"
cat "$source_dir/cogs/music.py" > "$app_dir/cogs/music.py"
cat "$source_dir/requirements.txt" > "$app_dir/requirements.txt"
systemctl restart honorary-bot.service
sleep 3
systemctl is-active --quiet honorary-bot.service
trap - ERR
echo "반영 완료. 백업: $backup_dir"
echo 'Discord에서 실제 재생 여부를 확인하세요. 서비스 active만으로 재생 성공을 보장하지 않습니다.'
