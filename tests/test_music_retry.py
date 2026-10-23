import asyncio
import unittest
from collections import deque
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from cogs.music import Music, MusicStreamError, PlayerState, Track


class StreamRetryTests(unittest.IsolatedAsyncioTestCase):
    async def _play(self, failures):
        music = Music(SimpleNamespace(loop=asyncio.get_running_loop()))
        channel = SimpleNamespace(send=AsyncMock())
        track = Track('chosen song', 'https://youtube.com/watch?v=chosen', 200, None,
                      'test', channel, stream_url='old-signed-url')
        state = PlayerState(queue=deque([track]))
        voice = Mock()
        voice.is_connected.return_value = True
        voice.is_playing.return_value = False
        calls = []

        def play(source, *, after):
            calls.append(track.webpage_url)
            after(MusicStreamError('stream failed') if len(calls) <= failures else None)

        voice.play.side_effect = play
        guild = SimpleNamespace(id=1, voice_client=voice)
        with patch.object(music, '_stream_url', AsyncMock(return_value='new-signed-url')), \
                patch.object(music, '_find_dashboard_message', AsyncMock(return_value=None)), \
                patch.object(music, '_temporary_channel_message', AsyncMock()) as notice, \
                patch('cogs.music.discord.FFmpegPCMAudio'), \
                patch('cogs.music.PlaybackVolumeTransformer'), \
                patch('cogs.music.schedule_idle'):
            await music._player_loop(guild, state)
            notices = notice.await_count
        return track, calls, notices

    async def test_retries_selected_video_once_without_changing_song(self):
        track, calls, notices = await self._play(failures=1)
        self.assertEqual(calls, ['https://youtube.com/watch?v=chosen'] * 2)
        self.assertEqual(track.stream_retry_count, 1)
        self.assertIsNone(track.stream_url)
        self.assertEqual(notices, 0)

    async def test_persistent_failure_stops_retrying_and_reports_error(self):
        _, calls, notices = await self._play(failures=99)
        self.assertEqual(len(calls), 2)
        self.assertEqual(notices, 1)

    async def test_normal_playback_is_not_retried(self):
        _, calls, notices = await self._play(failures=0)
        self.assertEqual(len(calls), 1)
        self.assertEqual(notices, 0)
