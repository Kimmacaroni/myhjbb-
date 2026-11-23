"""Install the pinned extractor as honorary-bot without changing the root venv.

Run under the service account. The bot loads this directory when present;
fresh environments can instead install requirements.txt normally.
"""
import hashlib
import io
from pathlib import Path
import tempfile
import urllib.request
import zipfile

VERSION = '2026.10.26'
WHEEL_URL = 'https://files.pythonhosted.org/packages/7f/3d/16ea7d5638cf585991f2c5705e8083688dde633d32d0871f2404e0f4d827/yt_dlp-2026.10.26-py3-none-any.whl'
SHA256 = 'a05c5b5d8562f7e8a62f5334348b406af4930d56d3a65f8021d14af0e22339ae'


def install():
    target = Path('/var/lib/honorary-bot/runtime') / f'yt-dlp-{VERSION}'
    if target.is_dir():
        print(f'yt-dlp {VERSION} runtime already installed')
        return
    with urllib.request.urlopen(WHEEL_URL, timeout=20) as response:
        wheel = response.read(16 * 1024 * 1024)
    if hashlib.sha256(wheel).hexdigest() != SHA256:
        raise RuntimeError('yt-dlp wheel integrity check failed')
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=target.parent) as directory:
        stage = Path(directory) / 'package'
        stage.mkdir()
        with zipfile.ZipFile(io.BytesIO(wheel)) as archive:
            for name in archive.namelist():
                if Path(name).is_absolute() or '..' in Path(name).parts:
                    raise RuntimeError('invalid wheel path')
            archive.extractall(stage)
        stage.rename(target)
    print(f'yt-dlp {VERSION} runtime installed')


if __name__ == '__main__':
    install()
