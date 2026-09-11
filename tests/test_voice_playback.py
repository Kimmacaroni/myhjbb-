from __future__ import annotations

import unittest

from voice_playback import start_playback, wait_for_playback


class FakeVoice:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.source = None

    def play(self, source, *, after) -> None:
        self.source = source
        after(self.error)
        after(RuntimeError("중복 콜백은 무시되어야 함"))


class VoicePlaybackTest(unittest.IsolatedAsyncioTestCase):
    async def test_start_playback_starts_before_future_is_awaited(self) -> None:
        voice = FakeVoice()
        finished = start_playback(voice, "audio")
        self.assertEqual(voice.source, "audio")
        self.assertIsNone(await finished)

    async def test_wait_for_playback_returns_callback_result(self) -> None:
        voice = FakeVoice()
        self.assertIsNone(await wait_for_playback(voice, "audio"))
        self.assertEqual(voice.source, "audio")

    async def test_wait_for_playback_preserves_error(self) -> None:
        error = RuntimeError("재생 실패")
        self.assertIs(await wait_for_playback(FakeVoice(error), object()), error)


if __name__ == "__main__":
    unittest.main()
