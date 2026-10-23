import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from cogs.updater import Updater


class UpdaterAccountTests(unittest.IsolatedAsyncioTestCase):
    async def test_service_account_gets_actionable_response_without_launching_root_job(self):
        interaction = SimpleNamespace(user=SimpleNamespace(id=1),
                                      response=SimpleNamespace(send_message=AsyncMock()))
        with patch('cogs.updater.is_bot_owner', return_value=True), \
                patch('cogs.updater.os.geteuid', return_value=1000), \
                patch('cogs.updater.asyncio.create_subprocess_exec', AsyncMock()) as launch:
            await Updater.update.callback(Updater(None), interaction)
        launch.assert_not_awaited()
        self.assertIn('Codex', interaction.response.send_message.call_args.args[0])

    async def test_owner_check_still_applies(self):
        interaction = SimpleNamespace(user=SimpleNamespace(id=1),
                                      response=SimpleNamespace(send_message=AsyncMock()))
        with patch('cogs.updater.is_bot_owner', return_value=False):
            await Updater.update.callback(Updater(None), interaction)
        self.assertIn('소유자', interaction.response.send_message.call_args.args[0])
