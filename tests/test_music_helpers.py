from __future__ import annotations

import unittest

from music_helpers import duration_text, progress_text


class MusicHelpersTest(unittest.TestCase):
    def test_duration_text_preserves_existing_formats(self) -> None:
        self.assertEqual(duration_text(None), "알 수 없음")
        self.assertEqual(duration_text(0), "알 수 없음")
        self.assertEqual(duration_text(65), "1:05")
        self.assertEqual(duration_text(3661), "1:01:01")

    def test_progress_text_accounts_for_seek_and_clamps_to_duration(self) -> None:
        self.assertEqual(
            progress_text(start_at=30, duration=60, started_at=10.0, now=40.0),
            "━━━━━━━━━━━━━━🔘\n`1:00 / 1:00`",
        )

    def test_progress_text_handles_clock_skew_and_unknown_duration(self) -> None:
        self.assertEqual(
            progress_text(start_at=10, duration=100, started_at=50.0, now=40.0),
            "━🔘━━━━━━━━━━━━━\n`0:10 / 1:40`",
        )
        self.assertEqual(
            progress_text(start_at=0, duration=None, started_at=0.0, now=5.0),
            "🔘 `재생 시간 확인 중`",
        )


if __name__ == "__main__":
    unittest.main()
