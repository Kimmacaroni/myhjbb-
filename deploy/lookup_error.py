"""Read a sanitized incident by the reference the user sends to Codex."""
import json
from pathlib import Path
import re
import sys

if len(sys.argv) != 2 or not re.fullmatch(r'HB-[A-Z][0-9]{3}-[A-F0-9]{12}', sys.argv[1].upper()):
    raise SystemExit('사용법: python3 deploy/lookup_error.py HB-M103-조회코드12자리')
path = Path('/dev/shm/honorary-bot-error-index') / (sys.argv[1].upper() + '.json')
try:
    payload = json.loads(path.read_text())
except (OSError, ValueError):
    raise SystemExit('조회 기록을 읽을 수 없습니다. 코드와 해당 서버를 확인해 주세요.')
print(json.dumps(payload, ensure_ascii=False, indent=2))
