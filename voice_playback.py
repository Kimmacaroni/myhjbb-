"""Discord 음성 재생 완료 콜백을 await 가능한 형태로 연결합니다."""

from __future__ import annotations

import asyncio
from typing import Any


def start_playback(voice: Any, source: Any) -> asyncio.Future[Exception | None]:
    """음성 소스를 즉시 재생하고 완료 결과 Future를 반환합니다."""
    loop = asyncio.get_running_loop()
    finished: asyncio.Future[Exception | None] = loop.create_future()

    def after_playing(error: Exception | None) -> None:
        def mark_finished() -> None:
            if not finished.done():
                finished.set_result(error)

        loop.call_soon_threadsafe(mark_finished)

    voice.play(source, after=after_playing)
    return finished


async def wait_for_playback(voice: Any, source: Any) -> Exception | None:
    """음성 소스를 재생하고 Discord의 after 콜백 결과를 기다립니다."""
    finished = start_playback(voice, source)
    return await finished
