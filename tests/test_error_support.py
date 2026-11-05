import json
from pathlib import Path
import re
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import db
from cogs.help import Help
from music_matching import MusicLookupError


class ErrorSupportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmp.name) / 'test.db')
        self.index = Path(self.tmp.name) / 'index'
        self.override = patch.object(db, 'ERROR_INDEX', self.index)
        self.override.start()
        db.init(self.db_path)

    def tearDown(self):
        db.close()
        self.override.stop()
        self.tmp.cleanup()

    def test_categories(self):
        cases = [(MusicLookupError('검색어 불일치'), 'music.search', 'HB-M101'),
                 (RuntimeError('Video unavailable'), 'music.search', 'HB-M102'),
                 (RuntimeError("Sign in to confirm you’re not a bot"), 'music.search', 'HB-M103'),
                 (MusicLookupError('뮤직비디오는 재생하지 않습니다.'), 'music.search', 'HB-M106'),
                 (RuntimeError('403 from chart service'), 'music.chart', 'HB-M107'),
                 (TimeoutError(), 'tts', 'HB-S101'),
                 (RuntimeError('unknown'), 'tts', 'HB-T101')]
        for error, context, expected in cases:
            self.assertEqual(db.error_code(error, context), expected)

    def test_incident_survives_restart_and_is_guild_scoped(self):
        response = db.report_error(TimeoutError(), 'music.search', 1)
        reference = re.search(r'HB-S101-[A-F0-9]{12}', response).group()
        db.close()
        db.init(self.db_path)
        self.assertEqual(db.lookup_error(reference, 1)['code'], 'HB-S101')
        self.assertIsNone(db.lookup_error(reference, 2))

    def test_diagnostic_never_contains_exception_text_or_input(self):
        try:
            raise RuntimeError('SECRET_TOKEN https://example.com/?token=secret user_search_query')
        except RuntimeError as error:
            response = db.report_error(error, 'command', 1)
        path = next(self.index.glob('*.json'))
        payload = json.loads(path.read_text())
        self.assertTrue(payload['frames'])
        for private in ('SECRET_TOKEN', '?token=', 'user_search_query'):
            self.assertNotIn(private, path.read_text() + response)

    def test_index_failure_does_not_break_user_response_or_db(self):
        with patch.object(db, 'prepare_error_index', side_effect=PermissionError()):
            response = db.report_error(TimeoutError(), 'command', 1)
        reference = re.search(r'HB-S101-[A-F0-9]{12}', response).group()
        self.assertIsNotNone(db.lookup_error(reference, 1))

    def test_each_occurrence_has_distinct_reference(self):
        a = db.report_error(TimeoutError(), 'command', 1)
        b = db.report_error(TimeoutError(), 'command', 1)
        self.assertNotEqual(a, b)

    def test_shared_cache_can_be_rebuilt_from_persistent_database(self):
        response = db.report_error(TimeoutError(), 'command', 1)
        reference = re.search(r'HB-S101-[A-F0-9]{12}', response).group()
        path = self.index / (reference + '.json')
        path.unlink()
        db.rebuild_error_index()
        self.assertEqual(json.loads(path.read_text())['reference'], reference)


class ErrorHelpTests(unittest.IsolatedAsyncioTestCase):
    async def test_catalog_without_database_lookup(self):
        interaction = SimpleNamespace(response=SimpleNamespace(send_message=AsyncMock()))
        await Help.error_help.callback(Help(None), interaction)
        self.assertIn('HB-M103', interaction.response.send_message.call_args.args[0])

    async def test_unknown_reference_is_not_exposed_across_servers(self):
        interaction = SimpleNamespace(guild=SimpleNamespace(id=2),
                                      response=SimpleNamespace(send_message=AsyncMock()))
        with patch('cogs.help.db.lookup_error', return_value=None) as lookup:
            await Help.error_help.callback(Help(None), interaction, 'HB-S101-123456789ABC')
            lookup.assert_called_once_with('HB-S101-123456789ABC', 2)
        self.assertIn('찾지 못했습니다', interaction.response.send_message.call_args.args[0])
