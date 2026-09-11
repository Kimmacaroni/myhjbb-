#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="/opt/honorary-bot"
REPOSITORY="Kimmacaroni/myhjbb-"
BRANCH="claude/how-it-works-x3928d"
STATUS_FILE="$APP_DIR/.update-status"
LOCK_FILE="$APP_DIR/.update.lock"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  printf '%s\n' "$(date -Is) 업데이트 실패: 이미 업데이트가 진행 중입니다." > "$STATUS_FILE"
  exit 1
fi

work_dir="$(mktemp -d)"
cleanup() { rm -rf -- "$work_dir"; }
trap cleanup EXIT
trap 'printf "%s\n" "$(date -Is) 업데이트 실패: ${BASH_LINENO[0]}번째 줄" > "$STATUS_FILE"' ERR

printf '%s\n' "$(date -Is) GitHub 최신 버전을 확인하는 중입니다." > "$STATUS_FILE"
archive_url="https://github.com/$REPOSITORY/archive/refs/heads/$BRANCH.tar.gz"
curl --fail --location --silent --show-error "$archive_url" -o "$work_dir/source.tar.gz"
mkdir "$work_dir/source"
tar -xzf "$work_dir/source.tar.gz" --strip-components=1 -C "$work_dir/source"

"$APP_DIR/.venv/bin/python" -m py_compile \
  "$work_dir/source/bot.py" \
  "$work_dir/source/db.py" \
  "$work_dir/source/config.py" \
  "$work_dir/source"/cogs/*.py
"$APP_DIR/.venv/bin/pip" install --quiet -r "$work_dir/source/requirements.txt"

# GitHub에 없는 운영 비밀값과 영구 데이터(.env, DB, 쿠키, models)는 건드리지 않습니다.
cp -a "$work_dir/source/." "$APP_DIR/"
chmod +x "$APP_DIR/deploy/update_from_github.sh"

commit="$(curl --fail --silent "https://api.github.com/repos/$REPOSITORY/commits/$BRANCH" \
  | "$APP_DIR/.venv/bin/python" -c 'import json,sys; print(json.load(sys.stdin)["sha"][:7])' \
  || printf 'latest')"
printf '%s\n' "$(date -Is) 업데이트 완료: $commit (서비스 재시작 중)" > "$STATUS_FILE"
systemctl restart honorary-bot.service
