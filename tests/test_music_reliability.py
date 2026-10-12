import asyncio
import unittest
from unittest.mock import patch, AsyncMock, Mock
from types import SimpleNamespace

from cogs.music import Music, Track
from music_matching import MusicLookupError, matches_query


def candidate(title, channel="IU - Topic"):
    return {"title": title, "channel": channel, "url": "https://www.youtube.com/watch?v=test"}


class QueryMatchingTests(unittest.TestCase):
    def test_matching_artist_and_song(self):
        self.assertTrue(matches_query("IU Love", candidate("Love (Official Audio)")))

    def test_wrong_song_even_on_correct_channel(self):
        self.assertFalse(matches_query("IU Love", candidate("Celebrity (Official Audio)")))

    def test_wrong_artist(self):
        self.assertFalse(matches_query("IU Love", candidate("Love", "Other Artist - Topic")))

    def test_short_title_is_not_prefix_of_other_title(self):
        self.assertFalse(matches_query("IU Love", candidate("Lovely")))
        self.assertFalse(matches_query("IU Love", candidate("Love Again")))

    def test_korean_spacing(self):
        self.assertTrue(matches_query("아이유 좋은날", candidate("좋은 날", "아이유 - Topic")))

    def test_missing_title_is_rejected(self):
        self.assertFalse(matches_query("IU", candidate("", "IU - Topic")))

    def test_official_score_cannot_override_relevance(self):
        with patch.object(Music, "_search_music_candidates", return_value=[
            candidate("Celebrity Official Audio"), candidate("Love")
        ]):
            self.assertEqual(Music._find_music_candidate("IU Love")["title"], "Love")

    def test_all_mismatches_fail_without_fallback_song(self):
        with patch.object(Music, "_search_music_candidates", return_value=[candidate("Celebrity")]):
            with self.assertRaises(MusicLookupError):
                Music._find_music_candidate("IU Love")

    def test_cover_is_never_chosen(self):
        with patch.object(Music, "_search_music_candidates", return_value=[candidate("IU Love Cover")]):
            with self.assertRaises(MusicLookupError):
                Music._find_music_candidate("IU Love Cover")

    def test_lookup_error_message_survives_sanitizing(self):
        self.assertEqual(Music._safe_music_error(MusicLookupError("일치하는 음원 없음"), "fallback"),
                         "일치하는 음원 없음")

    def test_stream_metadata_mismatch_is_rejected_before_play(self):
        track = Track("Love", "url", None, None, "requester", None,
                      requested_query="IU Love")
        with patch.object(Music, "_extract", return_value=candidate("Celebrity")):
            with self.assertRaises(MusicLookupError):
                Music._resolve_stream_info(track)

    def test_live_substring_inside_song_name_is_allowed(self):
        with patch.object(Music, "_search_music_candidates", return_value=[candidate("Believe")]):
            self.assertEqual(Music._find_music_candidate("IU Believe")["title"], "Believe")


class LookupTimeoutTests(unittest.IsolatedAsyncioTestCase):
    async def test_search_failure_never_joins_voice(self):
        music = Music(None)
        interaction = SimpleNamespace(
            response=SimpleNamespace(defer=AsyncMock()),
            followup=SimpleNamespace(send=AsyncMock()),
            user=SimpleNamespace(display_name="test", voice=SimpleNamespace(channel=Mock())),
            channel=Mock(),
        )
        with patch.object(music, "_track_from_query", AsyncMock(side_effect=MusicLookupError("없음"))), \
                patch.object(music, "_connect_for", AsyncMock()) as connect:
            await Music.play.callback(music, interaction, "IU Love")
            connect.assert_not_awaited()
            interaction.followup.send.assert_awaited_once_with("❌ 없음", ephemeral=True)

    async def test_stream_failure_never_joins_voice(self):
        music = Music(None)
        interaction = SimpleNamespace(
            response=SimpleNamespace(defer=AsyncMock()),
            followup=SimpleNamespace(send=AsyncMock()),
            user=SimpleNamespace(display_name="test", voice=SimpleNamespace(channel=Mock())),
            channel=Mock(),
        )
        with patch.object(music, "_track_from_query", AsyncMock(return_value=Mock())), \
                patch.object(music, "_stream_url", AsyncMock(side_effect=RuntimeError("blocked"))), \
                patch.object(music, "_connect_for", AsyncMock()) as connect:
            await Music.play.callback(music, interaction, "IU Love")
            connect.assert_not_awaited()
            interaction.followup.send.assert_awaited_once()

    async def test_slow_search_returns_timeout(self):
        music = Music(None)

        async def slow(*args):
            await asyncio.sleep(10)

        with patch("cogs.music.asyncio.to_thread", side_effect=slow), \
                patch("cogs.music.LOOKUP_TIMEOUT_SECONDS", 0.01):
            with self.assertRaises(TimeoutError):
                await music._track_from_query("IU Love", "requester", None)

    async def test_stream_timeout_releases_track_task(self):
        music = Music(None)
        track = Track("Love", "url", None, None, "requester", None)

        async def slow(*args):
            await asyncio.sleep(10)

        with patch("cogs.music.asyncio.to_thread", side_effect=slow), \
                patch("cogs.music.LOOKUP_TIMEOUT_SECONDS", 0.01):
            with self.assertRaises(TimeoutError):
                await music._stream_url(track)
            self.assertIsNone(track.stream_task)


if __name__ == "__main__":
    unittest.main()
