import asyncio
import unittest
from unittest.mock import patch, AsyncMock, Mock
from types import SimpleNamespace

from cogs.music import Music, Track
from music_matching import MusicLookupError, matches_query, query_score


def candidate(title, channel="IU - Topic"):
    return {"title": title, "channel": channel, "url": "https://www.youtube.com/watch?v=test"}


class QueryMatchingTests(unittest.TestCase):
    def test_unregistered_foreign_pronunciation_uses_youtube_music_rank(self):
        item = {**candidate('Poker Face (Official Audio)', 'Lady Gaga - Topic'), 'id': 'poker'}
        with patch.object(Music, '_search_music_candidates', return_value=[item]):
            selected = Music._find_music_candidate('레이디가가 포커페이스')
        self.assertEqual(selected['id'], 'poker')
        self.assertTrue(selected['_search_rank_inferred'])

    def test_cross_script_fallback_never_chooses_cover(self):
        item = {**candidate('Poker Face Cover Lyrics', 'Other'), 'id': 'cover'}
        with patch.object(Music, '_search_music_candidates', return_value=[item]):
            with self.assertRaises(MusicLookupError):
                Music._find_music_candidate('레이디가가 포커페이스')

    def test_inferred_stream_checks_video_identity_instead_of_korean_spelling(self):
        track = Track('Poker Face', 'url', None, None, 'requester', None,
                      requested_query='레이디가가 포커페이스', selected_video_id='poker')
        with patch.object(Music, '_extract', return_value={'id': 'poker', 'title': 'Poker Face'}):
            self.assertEqual(Music._resolve_stream_info(track)['id'], 'poker')
        with patch.object(Music, '_extract', return_value={'id': 'other', 'title': 'Poker Face'}):
            with self.assertRaises(MusicLookupError):
                Music._resolve_stream_info(track)

    def test_cl_iconic_with_korean_artist_suffix(self):
        item = candidate('CL - ‘ICONIC’ (Official Audio)', 'CL')
        for query in ('씨엘에 아이코닉', '씨엘 아이코닉', 'CL ICONIC'):
            self.assertTrue(matches_query(query, item), query)

    def test_2ne1_fire_korean_spellings_and_typos(self):
        item = candidate('2NE1 - FIRE (Official Audio)', '2NE1')
        for query in ('투앤이원 퐈이어', '투엔이원 파이어', '2ne1 fire',
                      '투애니원 파이어', '파이어 투앤이원', '2nei fier'):
            self.assertTrue(matches_query(query, item), query)

    def test_typos_in_artist_and_title_are_accepted(self):
        self.assertTrue(matches_query('Younha 사건의 지평션', candidate('사건의 지평선', 'YOUNHA')))
        self.assertTrue(matches_query('Ateez Adrenalin', candidate('Adrenaline', 'ATEEZ')))

    def test_relevance_wins_over_official_upload_score(self):
        exact = candidate('2NE1 - FIRE', '2NE1')
        close = candidate('2NE1 - FIRES Official Audio', '2NE1 - Topic')
        with patch.object(Music, '_search_music_candidates', return_value=[close, exact]):
            self.assertEqual(Music._find_music_candidate('투앤이원 퐈이어'), exact)
        self.assertGreater(query_score('2ne1 fire', exact), query_score('2ne1 fire', close))

    def test_typo_match_is_rechecked_when_resolving_stream(self):
        track = Track('FIRE', 'url', None, None, 'requester', None, requested_query='2nei fier')
        with patch.object(Music, '_extract', return_value=candidate('FIRE', '2NE1')):
            self.assertEqual(Music._resolve_stream_info(track)['title'], 'FIRE')

    def test_search_uses_plain_query_before_optional_fallbacks(self):
        with patch.object(Music, '_search_music_candidates', return_value=[candidate('Love')]) as search:
            Music._find_music_candidate('IU Love')
        search.assert_called_once_with('IU Love')

    def test_search_accepts_upload_descriptions_and_search_hints(self):
        for title in ('Love [고음질]', 'Love (Official Lyric Video)',
                      'Love [Lyrics/가사/해석]', 'Love [4K]',
                      'Love (Original Animation Soundtrack)'):
            self.assertTrue(matches_query('IU Love 가사', candidate(title)), title)

    def test_english_spacing_without_partial_song_match(self):
        self.assertTrue(matches_query('IVE LoveDive', candidate('Love Dive', 'IVE - Topic')))
        self.assertTrue(matches_query('IVE Love Dive', candidate('LoveDive', 'IVE - Topic')))
        self.assertFalse(matches_query('Other LoveDive', candidate('Love Dive', 'IVE - Topic')))
        self.assertFalse(matches_query('IU Love', candidate('Love Again')))

    def test_relaxed_labels_do_not_remove_versions_or_unknown_titles(self):
        for title in ('Love (Live)', 'Love [Cover]', 'Love (Speed Up)',
                      'Love (다른곡)', 'Love [Lyrics/Other Song]'):
            self.assertFalse(matches_query('IU Love', candidate(title)), title)

    def test_tula_power_up_spelling(self):
        item = candidate('Power UP', '열혈툴라 [TULA]')
        for query in ('파워업 툴라', '툴라 파워업', 'TULA Power Up'):
            self.assertTrue(matches_query(query, item), query)

    def test_tula_power_up_rejects_other_artist_and_versions(self):
        for title, channel in [('Power Up', 'Red Velvet'),
                               ('Power UP Instrumental', '열혈툴라 [TULA]'),
                               ('Power Up Live', '열혈툴라 [TULA]'),
                               ('Power Up 2020Ver.', '열혈툴라 [TULA]'),
                               ('Break Up', '열혈툴라 [TULA]')]:
            self.assertFalse(matches_query('파워업 툴라', candidate(title, channel)), title)

    def test_tula_power_up_selects_unmodified_song(self):
        items = [candidate('Power UP Instrumental', '열혈툴라 [TULA]'),
                 candidate('Power UP', '열혈툴라 [TULA]')]
        with patch.object(Music, '_search_music_candidates', return_value=items):
            self.assertEqual(Music._find_music_candidate('파워업 툴라'), items[1])

    def test_adrenaline_korean_spelling_and_artist_order(self):
        item = candidate("ATEEZ 에이티즈 'Adrenaline' Official Audio", 'JXS_BP Official')
        for query in ('아드레날린 에이티즈', '에이티즈 아드레날린', 'ATEEZ Adrenaline'):
            with self.subTest(query=query):
                self.assertTrue(matches_query(query, item))
        self.assertTrue(matches_query('아드레날린 에이티즈', candidate('Adrenaline', 'ATEEZ')))

    def test_adrenaline_alias_preserves_song_artist_and_version_checks(self):
        for title, channel in [('Adrenaline', 'Other Artist'),
                               ('Other Song', 'ATEEZ'),
                               ('Adrenaline (Speed Up Ver.)', 'ATEEZ'),
                               ('Adrenaline (NO1 Ver.)', 'ATEEZ'),
                               ('Adrenaline Again', 'ATEEZ')]:
            with self.subTest(title=title, channel=channel):
                self.assertFalse(matches_query('아드레날린 에이티즈', candidate(title, channel)))

    def test_adrenaline_search_skips_modified_version(self):
        items = [candidate('Adrenaline (Speed Up Ver.)', 'ATEEZ'),
                 candidate("ATEEZ 에이티즈 'Adrenaline' Official Audio", 'JXS_BP Official')]
        with patch.object(Music, '_search_music_candidates', return_value=items):
            self.assertEqual(Music._find_music_candidate('아드레날린 에이티즈'), items[1])

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

    def test_partial_artist_and_exact_song_title(self):
        self.assertTrue(matches_query('a20 neon', candidate("A20 LITE - 'NEON' Official Audio", 'A2O FAMILY')))

    def test_partial_artist_does_not_allow_another_song(self):
        self.assertFalse(matches_query('a20 neon', candidate("A20 LITE - 'SUPERSTAR' Official Audio", 'A2O FAMILY')))
        self.assertFalse(matches_query('a20 neon', candidate("A20 LITE - 'NEON AGAIN' Official Audio", 'A2O FAMILY')))
        self.assertFalse(matches_query('a20 neon', candidate("Other Artist - 'NEON' Official Audio", 'A20 FAMILY')))

    def test_digit_and_letter_are_not_silently_interchanged(self):
        self.assertFalse(matches_query('a20 neon', candidate("A2O LITE - 'NEON' Official Audio", 'A2O FAMILY')))

    def test_artist_alias_and_mixed_lyrics_label(self):
        self.assertTrue(matches_query('아이유 좋은날', candidate('아이유(IU) - 좋은 날 [가사/Lyrics]', '웅키')))
        self.assertTrue(matches_query('윤하 사건의 지평선', candidate('윤하(YOUNHA) - 사건의 지평선 [가사/Lyrics]', '웅키')))

    def test_artist_name_alone_does_not_match_song(self):
        self.assertFalse(matches_query('A20 LITE', candidate("A20 LITE - 'NEON' Official Audio", 'A2O FAMILY')))

    def test_a20_neon_search_finds_exact_audio(self):
        items = [candidate("A2O LITE 'NEON' Official Video", 'A2O WORLD'),
                 candidate("A20 LITE - 'NEON' Official Audio", 'A2O FAMILY')]
        with patch.object(Music, '_search_music_candidates', return_value=items):
            self.assertEqual(Music._find_music_candidate('a20 neon')['title'], items[1]['title'])

    def test_cherryfilter_lyrics_annotation(self):
        self.assertTrue(matches_query("체리필터 내게로와",
                                     candidate("체리필터 내게로 와 (가사 첨부)", "All NORE")))

    def test_bilingual_korean_and_english_title(self):
        self.assertTrue(matches_query("체리필터 내게로와",
                                     candidate("체리필터 - 내게로 와 | Cherryfilter - Come to me",
                                               "cherryfilter")))

    def test_bilingual_does_not_allow_another_korean_song(self):
        self.assertFalse(matches_query("체리필터 내게로와",
                                      candidate("체리필터 - 오리 날다 | Cherryfilter - Flying Duck",
                                                "cherryfilter")))
        self.assertFalse(matches_query("체리필터 내게로와",
                                      candidate("체리필터 - 내게로 와 다시 | Cherryfilter - Come to me",
                                                "cherryfilter")))

    def test_unrecognized_annotations_are_not_removed(self):
        self.assertFalse(matches_query("체리필터 내게로와",
                                      candidate("체리필터 내게로 와 (다른곡)", "All NORE")))

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
    async def test_direct_url_allows_music_video_live_cover_and_instrumental(self):
        music = Music(None)
        for title in ('Official Music Video', 'Live Cover', 'Instrumental'):
            info = dict(title=title, webpage_url='https://youtube.com/watch?v=123',
                        url='https://audio.example/stream', http_headers={})
            with patch.object(music, '_extract', return_value=info), \
                 patch.object(music, '_find_music_candidate') as search:
                track = await music._track_from_query(' https://youtube.com/watch?v=123 ', 'user', None)
                self.assertIsNone(track.requested_query)
                self.assertEqual(await music._stream_url(track), info['url'])
                search.assert_not_called()

    async def test_search_metadata_cache_reuses_extraction_and_copies_results(self):
        Music._cached_search_candidates.cache_clear()
        with patch('cogs.music.yt_dlp.YoutubeDL') as factory:
            extract = factory.return_value.__enter__.return_value.extract_info
            extract.return_value = {'entries': [candidate('Love')]}
            with patch('cogs.music.time.monotonic', return_value=120):
                first = Music._search_music_candidates('cache-test')
                first[0]['title'] = 'mutated'
                second = Music._search_music_candidates('cache-test')
            self.assertEqual(second[0]['title'], 'Love')
            extract.assert_called_once()
            with patch('cogs.music.time.monotonic', return_value=181):
                Music._search_music_candidates('cache-test')
            self.assertEqual(extract.call_count, 2)
        Music._cached_search_candidates.cache_clear()

    async def test_search_failure_never_joins_voice(self):
        music = Music(None)
        interaction = SimpleNamespace(
            response=SimpleNamespace(defer=AsyncMock()),
            followup=SimpleNamespace(send=AsyncMock()),
            user=SimpleNamespace(display_name="test", voice=SimpleNamespace(channel=Mock())),
            channel=Mock(),
        )
        with patch.object(music, "_track_from_query", AsyncMock(side_effect=MusicLookupError("없음"))), \
                patch.object(music, "_connect_for", AsyncMock()) as connect, \
                patch("cogs.music.db.report_error", return_value="❌ 없음"):
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
                patch.object(music, "_connect_for", AsyncMock()) as connect, \
                patch("cogs.music.db.report_error", return_value="❌ 없음"):
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
