import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import discord
from discord.ext import commands

from cogs.announcements import AnnouncementModal, Announcements, announcement_payload, setup


class PayloadTests(unittest.TestCase):
    def test_embed_separates_title_and_body(self):
        payload = announcement_payload("운행 안내", "첫 줄\n둘째 줄", True)
        self.assertEqual(payload["embed"].title, "📢 운행 안내")
        self.assertEqual(payload["embed"].description, "첫 줄\n둘째 줄")
        self.assertNotIn("content", payload)

    def test_text_uses_heading_and_keeps_body(self):
        payload = announcement_payload("운행 안내", "첫 줄\n둘째 줄", False)
        self.assertEqual(payload["content"], "# 📢 운행 안내\n\n첫 줄\n둘째 줄")
        self.assertNotIn("embed", payload)

    def test_no_mass_mentions(self):
        for embedded in (True, False):
            payload = announcement_payload("안내", "@everyone <@123>", embedded)
            self.assertEqual(payload["allowed_mentions"].to_dict(), {"parse": []})

    def test_blank_and_oversized_messages_are_rejected(self):
        for title, body, embedded in ((" ", "내용", True), ("제목", " ", False),
                                      ("x" * 201, "내용", True),
                                      ("제목", "x" * 4001, True),
                                      ("제목", "x" * 2000, False)):
            with self.subTest(title=title[:10], embedded=embedded):
                with self.assertRaises(ValueError):
                    announcement_payload(title, body, embedded)


class CommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_cog_registers_two_admin_guild_commands(self):
        bot = commands.Bot(command_prefix="!", intents=discord.Intents.none())
        try:
            await setup(bot)
            notices = bot.tree.get_commands()
            self.assertEqual({c.name for c in notices}, {"공지임베드", "공지텍스트"})
            for command in notices:
                self.assertTrue(command.guild_only)
                self.assertTrue(command.default_permissions.administrator)
                self.assertTrue(command.checks)
        finally:
            await bot.close()

    async def test_modal_rechecks_permission_before_sending(self):
        channel = Mock()
        channel.send = AsyncMock()
        modal = AnnouncementModal(channel, True)
        interaction = SimpleNamespace(response=SimpleNamespace(send_message=AsyncMock()))
        with patch("cogs.announcements.admin_or_owner", AsyncMock(return_value=False)):
            await modal.on_submit(interaction)
        channel.send.assert_not_awaited()
        interaction.response.send_message.assert_awaited_once()

    async def test_submit_posts_and_confirms_privately(self):
        channel = Mock()
        channel.guild.id = 1
        channel.send = AsyncMock(return_value=SimpleNamespace(jump_url="https://discord.com/test"))
        modal = AnnouncementModal(channel, False)
        modal.heading._value = "운행 안내"
        modal.body._value = "공지 내용"
        interaction = SimpleNamespace(
            guild=SimpleNamespace(id=1),
            response=SimpleNamespace(send_message=AsyncMock(), defer=AsyncMock()),
            followup=SimpleNamespace(send=AsyncMock()),
        )
        with patch("cogs.announcements.admin_or_owner", AsyncMock(return_value=True)):
            await modal.on_submit(interaction)
        self.assertEqual(channel.send.call_args.kwargs["content"], "# 📢 운행 안내\n\n공지 내용")
        interaction.response.defer.assert_awaited_once_with(ephemeral=True)
        self.assertTrue(interaction.followup.send.call_args.kwargs["ephemeral"])

    async def test_other_guild_cannot_receive_notice(self):
        channel = Mock()
        channel.guild.id = 2
        channel.send = AsyncMock()
        modal = AnnouncementModal(channel, True)
        interaction = SimpleNamespace(guild=SimpleNamespace(id=1),
                                      response=SimpleNamespace(send_message=AsyncMock()))
        with patch("cogs.announcements.admin_or_owner", AsyncMock(return_value=True)):
            await modal.on_submit(interaction)
        channel.send.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
