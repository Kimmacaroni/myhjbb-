"""Create a package as codex, then pipe it into the fixed deployment controller."""
import base64
import json
from pathlib import Path
import runpy
import sys

root = Path(__file__).resolve().parents[1]
allowed = runpy.run_path(str(root / 'deploy/bot_control.py'))['ALLOWED']
names = sys.argv[1:]
if not names or not set(names) <= allowed:
    raise SystemExit('배포할 허용 Python 파일을 지정하세요.')
payload = {}
for name in names:
    path = root / name
    if path.is_symlink() or not path.is_file():
        raise SystemExit('일반 파일만 패키징할 수 있습니다.')
    payload[name] = base64.b64encode(path.read_bytes()).decode()
print(json.dumps(payload))
