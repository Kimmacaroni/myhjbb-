import shlex
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

import discord
from cogs.music import Music, Track, PlaybackVolumeTransformer, ffmpeg_before_options, DownloaderAudioSource, MediaHTTPError
from music_matching import MusicLookupError


class StreamErrorTests(unittest.TestCase):
    def test_rejected_separate_url_uses_native_transport_for_same_video(self):
        info = {'url': 'https://edge.googlevideo.com/playback', 'protocol': 'https',
                'webpage_url': 'https://www.youtube.com/watch?v=chosen'}
        response = SimpleNamespace(status=403, reason='Forbidden')
        with patch('cogs.music.yt_dlp.YoutubeDL') as factory:
            ydl = factory.return_value.__enter__.return_value
            ydl.extract_info.return_value = info
            ydl.urlopen.side_effect = MediaHTTPError(response)
            result = Music._extract(info['webpage_url'])
        self.assertTrue(result['_download_transport'])
        self.assertEqual(result['url'], info['webpage_url'])

    def test_selected_video_avoids_duplicate_extraction(self):
        track = Track('song', 'https://www.youtube.com/watch?v=chosen', None, None, 'user', None,
                      selected_video_id='chosen')
        with patch.object(Music, '_extract') as extract:
            info = Music._resolve_stream_info(track)
        self.assertTrue(info['_download_transport'])
        extract.assert_not_called()

    def test_native_transport_pipes_media_without_shell_or_files(self):
        process = Mock()
        process.poll.return_value = 0
        with patch('cogs.music.subprocess.Popen', return_value=process) as popen, \
             patch('discord.FFmpegPCMAudio.__init__', return_value=None) as ffmpeg:
            track = Track('song', 'https://youtube.com/watch?v=chosen', None, None, 'user', None)
            source = DownloaderAudioSource(track)
            args = popen.call_args.args[0]
            self.assertEqual(args[-1], track.webpage_url)
            self.assertIn('-o', args)
            self.assertNotIn('shell', popen.call_args.kwargs)
            self.assertTrue(ffmpeg.call_args.kwargs['pipe'])
            source.cleanup()

    def test_google_media_is_checked_before_returning_stream(self):
        info = {'url': 'https://edge.googlevideo.com/playback', 'protocol': 'https',
                'http_headers': {'User-Agent': 'test'}}
        with patch('cogs.music.yt_dlp.YoutubeDL') as factory:
            ydl = factory.return_value.__enter__.return_value
            ydl.extract_info.return_value = info
            ydl.urlopen.return_value.__enter__.return_value.read.return_value = b'audio'
            self.assertEqual(Music._extract('video'), info)
            request = ydl.urlopen.call_args.args[0]
            self.assertEqual(request.headers['Range'], 'bytes=0-4095')

    def test_empty_media_is_rejected_before_joining_voice(self):
        with patch('cogs.music.yt_dlp.YoutubeDL') as factory:
            ydl = factory.return_value.__enter__.return_value
            ydl.extract_info.return_value = {'url': 'https://edge.googlevideo.com/playback', 'protocol': 'https'}
            ydl.urlopen.return_value.__enter__.return_value.read.return_value = b''
            with self.assertRaises(MusicLookupError):
                Music._extract('video')

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

    def test_eof_before_process_error_is_reported_as_failure(self):
        audio = Mock(spec=discord.AudioSource)
        audio.is_opus.return_value = False
        audio.read.return_value = b''
        audio._current_error = None
        audio._stopped = False
        audio._process = Mock()
        audio._process.wait.return_value = 8
        source = PlaybackVolumeTransformer(audio)
        source.frames_read = 3
        with self.assertRaises(MusicLookupError):
            source.read()

    def test_no_audio_frames_is_not_successful_playback(self):
        audio = Mock(spec=discord.AudioSource)
        audio.is_opus.return_value = False
        audio.read.return_value = b''
        audio._current_error = None
        with self.assertRaises(MusicLookupError):
            PlaybackVolumeTransformer(audio).read()

    def test_normal_end_is_not_failure(self):
        audio = Mock(spec=discord.AudioSource)
        audio.is_opus.return_value = False
        audio.read.return_value = b''
        audio._current_error = None
        source = PlaybackVolumeTransformer(audio)
        source.frames_read = 10
        self.assertEqual(source.read(), b'')

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
