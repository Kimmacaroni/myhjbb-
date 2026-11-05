import base64
import json
import runpy
import unittest
from pathlib import Path

decode = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'deploy/bot_control.py'))['decode_release']


def release(name, content=b'print("test")'):
    return json.dumps({name: base64.b64encode(content).decode()}).encode()


class DeploymentPackageTests(unittest.TestCase):
    def test_python_module_is_accepted_without_execution(self):
        content = b'raise RuntimeError("must not execute as root")'
        self.assertEqual(decode(release('music_matching.py', content)), {'music_matching.py': content})

    def test_privileged_and_data_paths_are_rejected(self):
        for path in ('../sudoers', '/etc/sudoers', '.env', 'bot.db',
                     'youtube-cookies.txt', 'deploy/update_from_github.sh', 'cogs/../../root.py'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                decode(release(path))

    def test_syntax_error_is_rejected(self):
        with self.assertRaises(SyntaxError):
            decode(release('bot.py', b'if :'))

    def test_oversized_file_is_rejected(self):
        with self.assertRaises(ValueError):
            decode(release('bot.py', b'x' * (1024 * 1024 + 1)))

    def test_empty_release_is_rejected(self):
        with self.assertRaises(ValueError):
            decode(b'{}')
