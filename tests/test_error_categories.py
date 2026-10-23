import errno
import sqlite3
import unittest
from types import SimpleNamespace

import discord
import requests
import db


class ExpandedCategoriesTests(unittest.TestCase):
    def test_youtube_specific_failures(self):
        cases = {
            'Private video': 'HB-M108',
            'This video has been removed': 'HB-M109',
            'Video unavailable: not available in your country': 'HB-M110',
            'Sign in to confirm your age': 'HB-M111',
            'Requested format is not available': 'HB-M112',
            'Cookies have expired': 'HB-M113',
            'HTTP Error 429: Too Many Requests': 'HB-M114',
            'Unsupported URL': 'HB-M115',
            'Already playing audio': 'HB-M117',
        }
        for message, expected in cases.items():
            with self.subTest(message=message):
                self.assertEqual(db.error_code(RuntimeError(message), 'music.search'), expected)

    def test_storage_network_and_dependencies(self):
        cases = [(sqlite3.OperationalError('database is locked'), 'HB-S103'),
                 (sqlite3.DatabaseError('database disk image is malformed'), 'HB-S104'),
                 (OSError(errno.ENOSPC, 'No space'), 'HB-S105'),
                 (ImportError('module'), 'HB-S106'),
                 (requests.exceptions.ConnectionError('failed'), 'HB-S102'),
                 (requests.exceptions.Timeout('late'), 'HB-S101')]
        for error, expected in cases:
            self.assertEqual(db.error_code(error, 'command'), expected)

    def test_discord_detailed_codes(self):
        for status, code, expected in [(404,10062,'HB-D103'), (400,40060,'HB-D104'),
                                        (429,0,'HB-D105'), (503,0,'HB-D106'),
                                        (400,50035,'HB-D107')]:
            error = discord.HTTPException(SimpleNamespace(status=status, reason='test'),
                                          {'code': code, 'message': 'test'})
            self.assertEqual(db.error_code(error, 'command'), expected)
        error = discord.NotFound(SimpleNamespace(status=404, reason='test'), {'code': 10003,'message':'test'})
        self.assertEqual(db.error_code(error, 'command'), 'HB-D102')

    def test_tts_menu_and_announcement(self):
        cases = [(FileNotFoundError('model'), 'tts', 'HB-T102'),
                 (RuntimeError('unsupported voice'), 'tts', 'HB-T103'),
                 (ValueError('text too long'), 'tts', 'HB-T104'),
                 (MemoryError(), 'tts', 'HB-T105'),
                 (ValueError('오늘의 식단 정보가 없습니다.'), 'menu', 'HB-F102'),
                 (ValueError('Invalid JSON'), 'menu', 'HB-F103'),
                 (ValueError('제목은 200자까지 입력할 수 있습니다.'), 'announcement', 'HB-A102'),
                 (ValueError('제목과 내용을 모두 입력해 주세요.'), 'announcement', 'HB-A103')]
        for error, context, expected in cases:
            self.assertEqual(db.error_code(error, context), expected)

    def test_every_catalog_code_has_explanation_and_action_and_fits_list(self):
        for code, entry in db.ERROR_CATALOG.items():
            self.assertRegex(code, r'^HB-[A-Z][0-9]{3}$')
            self.assertTrue(all(entry))
        listing = '\n'.join(f'`{code}` — {item[0]}' for code, item in db.ERROR_CATALOG.items())
        self.assertLessEqual(len(listing), 2000)
