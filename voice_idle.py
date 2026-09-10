"""음성 채널 연결의 10분 유휴 퇴장을 공통 관리합니다."""

from __future__ import annotations

import asyncio
import logging

import discord
from discord.ext import commands

log = logging.getLogger(__name__)
IDLE_SECONDS = 10 * 60


def _tasks(bot: commands.Bot) -> dict[int, asyncio.Task]:
    tasks = getattr(bot, "voice_idle_tasks", None)
    if tasks is None:
        tasks = {}
        setattr(bot, "voice_idle_tasks", tasks)
    return tasks


def cancel_idle(bot: commands.Bot, guild_id: int) -> None:
    task = _tasks(bot).pop(guild_id, None)
    if task and not task.done():
        task.cancel()


def schedule_idle(bot: commands.Bot, guild: discord.Guild) -> None:
    """마지막 음성 명령으로부터 10분 후, 재생 중이 아니면 퇴장합니다."""
    cancel_idle(bot, guild.id)

    async def leave_when_idle() -> None:
        try:
            await asyncio.sleep(IDLE_SECONDS)
            voice = guild.voice_client
            if voice and voice.is_connected():
                if voice.is_playing():
                    schedule_idle(bot, guild)
                else:
                    await voice.disconnect()
                    log.info("[%s] 음성 채널 10분 유휴로 자동 퇴장", guild.name)
        except asyncio.CancelledError:
            pass
        finally:
            current = _tasks(bot).get(guild.id)
            if current is asyncio.current_task():
                _tasks(bot).pop(guild.id, None)

    _tasks(bot)[guild.id] = asyncio.create_task(leave_when_idle())
