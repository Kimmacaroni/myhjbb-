#!/usr/bin/env bash
# One-time root setup. Does not enable unrestricted sudo or change .env values.
set -Eeuo pipefail
[[ $EUID -eq 0 ]] || { echo '처음 설정은 root 콘솔에서 실행하세요.' >&2; exit 1; }
source_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
app_dir=/opt/honorary-bot
rule=/etc/sudoers.d/codex-honorary-bot
override=/etc/systemd/system/honorary-bot.service.d/90-deployment-account.conf
[[ ! -e "$rule" && ! -e "$override" && ! -e /var/lib/honorary-bot/bot.db ]] || {
  echo '기존 설정이 있어 자동으로 덮어쓰지 않습니다.' >&2; exit 1;
}
id codex >/dev/null
if ! id honorary-bot >/dev/null 2>&1; then
  useradd --system --user-group --home-dir /var/lib/honorary-bot --shell /usr/sbin/nologin honorary-bot
fi
install -d -m 700 -o honorary-bot -g honorary-bot /var/lib/honorary-bot
install -d -m 700 -o root -g root /var/lib/honorary-bot-backups
install -d -m 755 -o root -g root /usr/local/libexec/honorary-bot
install -o root -g root -m 755 "$source_dir/bot_control.py" /usr/local/sbin/honorary-bot-control
install -o root -g root -m 755 "$source_dir/bot_launch.py" /usr/local/libexec/honorary-bot/launch
backup_dir="$(mktemp -d /var/lib/honorary-bot-backups/account-XXXXXXXX)"
rule_tmp="$(mktemp)"
trap 'rm -f "$rule_tmp"' EXIT
cat > "$rule_tmp" <<'EOF'
codex ALL=(root) NOPASSWD: /usr/local/sbin/honorary-bot-control deploy, /usr/local/sbin/honorary-bot-control restart, /usr/local/sbin/honorary-bot-control status, /usr/local/sbin/honorary-bot-control logs
EOF
visudo -cf "$rule_tmp"
systemctl stop honorary-bot.service
rollback() {
  trap - ERR
  rm -f "$override" "$rule"
  # Existing operational data was never removed or overwritten.
  systemctl daemon-reload
  systemctl restart honorary-bot.service || true
  echo "전용 계정 전환 실패: 기존 서비스 설정으로 복구. 백업: $backup_dir" >&2
}
trap rollback ERR
# Read configured paths without printing secret values or evaluating shell code.
/usr/bin/python3 -I - "$app_dir" "$backup_dir" <<'PY'
import pathlib, shlex, shutil, sqlite3, sys
app = pathlib.Path(sys.argv[1]); backup = pathlib.Path(sys.argv[2])
settings = {}
for line in (app / '.env').read_text().splitlines():
    key, sep, value = line.strip().partition('=')
    if sep and key in ('DB_PATH', 'YTDLP_COOKIE_FILE'):
        words = shlex.split(value, comments=True)
        if words: settings[key] = words[0]
for key, default, destination in (
    ('DB_PATH', 'bot.db', 'bot.db'),
    ('YTDLP_COOKIE_FILE', 'youtube-cookies.txt', 'youtube-cookies.txt'),
):
    path = pathlib.Path(settings.get(key, default))
    if not path.is_absolute(): path = app / path
    if path.is_file():
        if key == 'DB_PATH':
            with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as source:
                with sqlite3.connect(backup / destination) as saved:
                    source.backup(saved)
            shutil.copy2(backup / destination, pathlib.Path('/var/lib/honorary-bot') / destination)
        else:
            shutil.copy2(path, backup / destination)
            shutil.copy2(path, pathlib.Path('/var/lib/honorary-bot') / destination)
    elif key == 'DB_PATH':
        raise RuntimeError('Configured database not found')
status = app / '.update-status'
if status.is_file(): shutil.copy2(status, '/var/lib/honorary-bot/.update-status')
PY
chown -R honorary-bot:honorary-bot /var/lib/honorary-bot
chmod 700 /var/lib/honorary-bot
chmod 600 /var/lib/honorary-bot/bot.db
if [[ -e /var/lib/honorary-bot/youtube-cookies.txt ]]; then
  chmod 600 /var/lib/honorary-bot/youtube-cookies.txt
fi
# Root must protect every code destination directory, including their parents.
chown root:root "$app_dir" "$app_dir/cogs" "$app_dir/experimental"
chmod 755 "$app_dir" "$app_dir/cogs" "$app_dir/experimental"
install -d -m 755 "$(dirname "$override")"
cat > "$override" <<'EOF'
[Service]
User=honorary-bot
Group=honorary-bot
ExecStart=
ExecStart=/usr/local/libexec/honorary-bot/launch
NoNewPrivileges=true
PrivateTmp=true
EOF
install -m 440 -o root -g root "$rule_tmp" "$rule"
visudo -cf /etc/sudoers
systemctl daemon-reload
started_at="$(date --iso-8601=seconds)"
systemctl start honorary-bot.service
ready=false
for attempt in {1..20}; do
  sleep 2
  systemctl is-active --quiet honorary-bot.service
  startup_log="$(journalctl -u honorary-bot.service --since "$started_at" --no-pager -o cat)"
  if [[ "$startup_log" == *'로그인 완료'* ]]; then ready=true; break; fi
done
[[ "$ready" == true ]] || { echo 'Discord 로그인 확인 실패' >&2; false; }
runuser -u codex -- sudo -n /usr/local/sbin/honorary-bot-control status
trap - ERR
echo "설정 완료. codex가 봇 배포·재시작·상태·로그 확인을 직접 수행할 수 있습니다. 백업: $backup_dir"
echo 'DB·쿠키 사용 경로는 /var/lib/honorary-bot이며 기존 원본과 .env·모델은 보존했습니다.'
