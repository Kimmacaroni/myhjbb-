#!/usr/bin/python3 -I
"""Root-owned, fixed-purpose controller. Deployed Python runs as honorary-bot."""
import base64
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

APP = Path('/opt/honorary-bot')
SERVICE = 'honorary-bot.service'
ALLOWED = {'bot.py', 'config.py', 'db.py', 'access_control.py', 'levels.py',
           'menu_source.py', 'traffic_source.py', 'melon_chart.py', 'voice_idle.py',
           'music_matching.py', 'music_queue.py',
           'experimental/huggingface_korean_tts.py'}
ALLOWED.update('cogs/' + name + '.py' for name in
               ('leveling', 'titles', 'menu', 'traffic', 'music', 'tts', 'updater',
                'help', 'announcements'))


def decode_release(raw):
    if len(raw) > 8 * 1024 * 1024:
        raise ValueError('release too large')
    payload = json.loads(raw)
    if not isinstance(payload, dict) or not payload or not set(payload) <= ALLOWED:
        raise ValueError('unapproved file path')
    files = {}
    for name, encoded in payload.items():
        content = base64.b64decode(encoded, validate=True)
        if len(content) > 1024 * 1024:
            raise ValueError('file too large')
        compile(content, name, 'exec')
        files[name] = content
    return files


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def restart():
    since = subprocess.check_output(['/usr/bin/date', '--iso-8601=seconds'], text=True).strip()
    run('/usr/bin/systemctl', 'restart', SERVICE)
    for _ in range(20):
        time.sleep(2)
        run('/usr/bin/systemctl', 'is-active', '--quiet', SERVICE)
        logs = subprocess.check_output(['/usr/bin/journalctl', '-u', SERVICE,
                                        '--since', since, '--no-pager', '-o', 'cat'], text=True)
        if '로그인 완료' in logs:
            return
    raise RuntimeError('bot login was not confirmed')


def deploy(files):
    # Root protects all destination directories. Never follow user-created links.
    for name in files:
        target = APP / name
        for part in (APP, target.parent, target):
            if part.is_symlink():
                raise ValueError('symlink destination')
        if target.parent.stat().st_uid != 0 or target.parent.stat().st_mode & 0o022:
            raise ValueError('unprotected destination directory')
    backup = Path(tempfile.mkdtemp(prefix='release-', dir='/var/lib/honorary-bot-backups'))
    old = {}
    for name in files:
        source = APP / name
        old[name] = source.exists()
        if source.exists():
            saved = backup / name
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, saved)
    try:
        for name, content in files.items():
            target = APP / name
            fd, temporary = tempfile.mkstemp(dir=target.parent)
            with os.fdopen(fd, 'wb') as out:
                out.write(content)
            os.chmod(temporary, 0o644)
            os.replace(temporary, target)
        restart()
    except Exception:
        for name, existed in old.items():
            if existed:
                shutil.copy2(backup / name, APP / name)
            else:
                (APP / name).unlink(missing_ok=True)
        restart()
        raise
    print('배포 완료. 백업:', backup)


def main():
    if os.geteuid() != 0 or len(sys.argv) != 2:
        raise ValueError('root controller requires one fixed action')
    action = sys.argv[1]
    if action == 'status':
        run('/usr/bin/systemctl', 'show', SERVICE, '-p', 'User', '-p', 'ActiveState',
            '-p', 'SubState', '-p', 'MainPID')
        return
    if action == 'logs':
        run('/usr/bin/journalctl', '-u', SERVICE, '--since', '10 minutes ago',
            '--no-pager', '-n', '100')
        return
    if action not in ('deploy', 'restart'):
        raise ValueError('unknown action')
    user = subprocess.check_output(['/usr/bin/systemctl', 'show', SERVICE,
                                    '-p', 'User', '--value'], text=True).strip()
    if user != 'honorary-bot':
        raise ValueError('service must run as honorary-bot')
    with open('/run/lock/honorary-bot-control.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if action == 'restart':
            restart()
        else:
            deploy(decode_release(sys.stdin.buffer.read(8 * 1024 * 1024 + 1)))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Do not echo untrusted source or credential-bearing exception details.
        print('작업 실패:', type(exc).__name__, file=sys.stderr)
        sys.exit(1)
