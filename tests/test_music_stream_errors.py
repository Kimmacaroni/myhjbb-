import shlex
import unittest
from unittest.mock import Mock, patch

import discord
from cogs.music import Music, Track, PlaybackVolumeTransformer, ffmpeg_before_options
from music_matching import MusicLookupError


class StreamErrorTests(unittest.TestCase):
    def test_http_headers_are_one_ffmpeg_argument(self):
        track = Track('song', 'url', None, None, 'test', None,
                      http_headers={'User-Agent': 'test agent', 'Referer': 'https://youtube.com/'})
        parts = shlex.split(ffmpeg_before_options(track))
        header = parts[parts.index('-headers') + 1]
        self.assertIn('User-Agent: test agent\r\n', header)
        self.assertIn('Referer: https://youtube.com/\r\n', header)

    def test_header_injection_is_rejected(self):
        track = Track('song', 'url', None, None, 'test', None,
                      http_headers={'Bad Header': 'x', 'User-Agent': 'x\r\nInjected: y'})
        self.assertNotIn('-headers', shlex.split(ffmpeg_before_options(track)))

    def test_seek_is_preserved_with_headers(self):
        track = Track('song', 'url', None, None, 'test', None, start_at=30)
        self.assertEqual(shlex.split(ffmpeg_before_options(track))[:2], ['-ss', '30'])

    def test_ffmpeg_failure_does_not_look_like_normal_end(self):
        audio = Mock(spec=discord.AudioSource)
        audio.is_opus.return_value = False
        audio.read.return_value = b''
        audio._current_error = RuntimeError('FFmpeg code 8 with private URL')
        source = PlaybackVolumeTransformer(audio)
        with self.assertRaises(MusicLookupError) as result:
            source.read()
        self.assertNotIn('private URL', str(result.exception))

    def test_normal_end_is_not_failure(self):
        audio = Mock(spec=discord.AudioSource)
        audio.is_opus.return_value = False
        audio.read.return_value = b''
        audio._current_error = None
        self.assertEqual(PlaybackVolumeTransformer(audio).read(), b'')

    def test_unavailable_video_has_specific_safe_message(self):
        message = Music._safe_music_error(RuntimeError('Video unavailable'), 'fallback')
        self.assertIn('현재 재생할 수 없습니다', message)


class HeaderPersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_extracted_headers_follow_cached_stream(self):
        track = Track('song', 'url', None, None, 'test', None)
        music = Music(None)
        with patch.object(Music, '_resolve_stream_info', return_value={
            'url': 'https://example.com/audio', 'http_headers': {'User-Agent': 'test'}
        }):
            await music._stream_url(track)
        self.assertEqual(track.http_headers, {'User-Agent': 'test'})

    async def test_direct_url_also_keeps_extraction_headers(self):
        music = Music(None)
        with patch.object(Music, '_extract', return_value={
            'title': 'Song Audio', 'webpage_url': 'https://youtube.com/watch?v=test',
            'url': 'https://example.com/audio', 'http_headers': {'User-Agent': 'test'}
        }):
            track = await music._track_from_query('https://youtube.com/watch?v=test', 'test', None)
        self.assertEqual(track.http_headers, {'User-Agent': 'test'})
