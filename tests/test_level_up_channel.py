import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import discord
import db
from cogs.leveling import Leveling


class LevelChannelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / 'test.db')
        db.init(self.path)

    def tearDown(self):
        db.close()
        self.tmp.cleanup()

    def test_guild_isolation_and_preservation_of_other_settings(self):
        db.set_menu_channel(1, 900)
        db.set_level_up_channel(1, 100)
        db.set_level_up_channel(2, 200)
        self.assertEqual(db.get_level_up_channel(1), 100)
        self.assertEqual(db.get_level_up_channel(2), 200)
        self.assertEqual(db.get_menu_channel(1), 900)
        db.set_level_up_channel(1, None)
        self.assertIsNone(db.get_level_up_channel(1))
        self.assertEqual(db.get_level_up_channel(2), 200)

    def test_setting_survives_restart(self):
        db.set_level_up_channel(1, 100)
        db.close()
        db.init(self.path)
        self.assertEqual(db.get_level_up_channel(1), 100)

    def test_configured_channel_wins_over_message_channel(self):
        chosen = Mock()
        guild = SimpleNamespace(id=1, get_channel=Mock(return_value=chosen), system_channel=Mock())
        db.set_level_up_channel(1, 100)
        self.assertIs(Leveling(None)._announce_channel(guild, Mock()), chosen)
        guild.get_channel.assert_called_once_with(100)

    def test_deleted_channel_does_not_leak_to_other_channel(self):
        guild = SimpleNamespace(id=1, get_channel=Mock(return_value=None), system_channel=Mock())
        db.set_level_up_channel(1, 100)
        self.assertIsNone(Leveling(None)._announce_channel(guild, Mock()))

    def test_default_message_channel_is_preserved(self):
        fallback = Mock()
        guild = SimpleNamespace(id=1, get_channel=Mock(), system_channel=Mock())
        with patch('cogs.leveling.config.LEVEL_UP_CHANNEL_ID', 0):
            self.assertIs(Leveling(None)._announce_channel(guild, fallback), fallback)

    def test_old_database_migration_preserves_rows(self):
        db.close()
        old_path = str(Path(self.tmp.name) / 'old.db')
        with sqlite3.connect(old_path) as conn:
            conn.execute('CREATE TABLE guild_settings (guild_id INTEGER PRIMARY KEY, menu_channel_id INTEGER)')
            conn.execute('INSERT INTO guild_settings VALUES (1, 900)')
        db.init(old_path)
        self.assertEqual(db.get_menu_channel(1), 900)
        self.assertIsNone(db.get_level_up_channel(1))
        db.set_level_up_channel(1, 100)
        self.assertEqual(db.get_level_up_channel(1), 100)


class LevelChannelCommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_permission_failure_does_not_save_channel(self):
        target = Mock(spec=discord.TextChannel)
        target.guild.id = 1
        target.permissions_for.return_value = SimpleNamespace(view_channel=True, send_messages=True, embed_links=False)
        interaction = SimpleNamespace(guild=SimpleNamespace(id=1, me=Mock()), channel=target,
                                      response=SimpleNamespace(send_message=AsyncMock()))
        with patch('cogs.leveling.db.set_level_up_channel') as save:
            await Leveling.set_level_channel.callback(Leveling(None), interaction)
            save.assert_not_called()
        self.assertIn('권한', interaction.response.send_message.call_args.args[0])

    async def test_setting_uses_current_channel_when_omitted(self):
        target = Mock(spec=discord.TextChannel)
        target.guild.id = 1
        target.id = 100
        target.mention = '<#100>'
        target.permissions_for.return_value = SimpleNamespace(view_channel=True, send_messages=True, embed_links=True)
        interaction = SimpleNamespace(guild=SimpleNamespace(id=1, me=Mock()), channel=target,
                                      response=SimpleNamespace(send_message=AsyncMock()))
        with patch('cogs.leveling.db.set_level_up_channel') as save:
            await Leveling.set_level_channel.callback(Leveling(None), interaction)
            save.assert_called_once_with(1, 100)

    async def test_new_commands_are_admin_and_guild_only(self):
        for command in (Leveling.set_level_channel, Leveling.clear_level_channel, Leveling.show_level_channel):
            self.assertTrue(command.guild_only)
            self.assertTrue(command.default_permissions.administrator)
            self.assertTrue(command.checks)
