import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from collections import deque

from cogs.music import Music, PlayerState
from music_queue import QueueView, queue_embed


def track(title):
    return SimpleNamespace(title=title)


class QueueTests(unittest.TestCase):
    def test_current_does_not_hide_empty_waiting_list(self):
        embed = queue_embed(track("현재곡"), [])
        self.assertIn("0곡 대기", embed.title)
        self.assertIn("대기 중인 곡이 없습니다", embed.description)
        self.assertEqual(embed.fields[0].value, "현재곡")

    def test_waiting_tracks_and_current_are_separate(self):
        embed = queue_embed(track("현재곡"), [track("다음곡"), track("그다음곡")])
        self.assertIn("2곡 대기", embed.title)
        self.assertIn("1.** 다음곡", embed.description)
        self.assertIn("2.** 그다음곡", embed.description)
        self.assertNotIn("현재곡", embed.description)

    def test_all_100_tracks_can_be_viewed(self):
        waiting = [track(f"노래{i}") for i in range(1, 101)]
        embed = queue_embed(None, waiting, 9)
        self.assertIn("100.** 노래100", embed.description)
        self.assertIn("10/10페이지", embed.footer.text)

    def test_long_titles_fit_discord_embed_limit(self):
        embed = queue_embed(track("*" * 1000), [track("*" * 1000) for _ in range(100)])
        self.assertLess(len(embed.description), 4096)
        self.assertLess(len(embed), 6000)


class QueueInteractionTests(unittest.IsolatedAsyncioTestCase):
    async def test_button_routes_to_full_queue_response(self):
        bot = SimpleNamespace()
        music = Music(bot)
        music.players[1] = PlayerState(queue=deque([track("다음곡")]), current=track("현재곡"))
        interaction = SimpleNamespace(guild=SimpleNamespace(id=1, voice_client=None),
                                      response=SimpleNamespace(send_message=AsyncMock()))
        with patch("cogs.music.cancel_idle"):
            await Music.queue.callback(music, interaction)
        embed = interaction.response.send_message.call_args.kwargs["embed"]
        self.assertIn("다음곡", embed.description)
        self.assertTrue(interaction.response.send_message.call_args.kwargs["ephemeral"])
        self.assertNotIn("view", interaction.response.send_message.call_args.kwargs)

    async def test_next_page_moves_to_remaining_tracks(self):
        view = QueueView(None, [track(f"노래{i}") for i in range(1, 12)])
        interaction = SimpleNamespace(response=SimpleNamespace(edit_message=AsyncMock()))
        await view.next.callback(interaction)
        self.assertEqual(view.page, 1)
        embed = interaction.response.edit_message.call_args.kwargs["embed"]
        self.assertIn("11.** 노래11", embed.description)
        self.assertTrue(view.next.disabled)
        self.assertFalse(view.previous.disabled)
