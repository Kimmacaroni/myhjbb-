"""GitHub 최신 코드를 운영 VPS에 반영하는 소유자 전용 명령어."""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from access_control import is_bot_owner

log = logging.getLogger(__name__)

UPDATE_SCRIPT = Path(os.getenv("BOT_UPDATE_SCRIPT", "/opt/honorary-bot/deploy/update_from_github.sh"))
UPDATE_STATUS = Path(os.getenv("BOT_UPDATE_STATUS", "/opt/honorary-bot/.update-status"))


class Updater(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="업데이트", description="GitHub 최신 버전으로 봇을 업데이트합니다. (봇 소유자 전용)")
    async def update(self, interaction: discord.Interaction):
        if not is_bot_owner(interaction.user):
            await interaction.response.send_message("이 명령어는 봇 소유자만 사용할 수 있습니다.", ephemeral=True)
            return
        if not UPDATE_SCRIPT.is_file():
            await interaction.response.send_message("업데이트 실행 파일을 찾지 못했습니다.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        try:
            process = await asyncio.create_subprocess_exec(
                "systemd-run",
                "--unit=honorary-bot-update",
                "--collect",
                str(UPDATE_SCRIPT),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            code = await process.wait()
        except Exception:
            log.exception("업데이트 작업 시작 실패")
            await interaction.followup.send("업데이트 작업을 시작하지 못했습니다.", ephemeral=True)
            return

        if code != 0:
            await interaction.followup.send(
                "이미 업데이트 중이거나 작업을 시작할 수 없습니다. `/업데이트상태`를 확인해 주세요.",
                ephemeral=True,
            )
            return
        await interaction.followup.send(
            "업데이트를 시작했습니다. 검사가 끝나면 봇이 자동으로 재시작됩니다. 잠시 후 `/업데이트상태`로 확인해 주세요.",
            ephemeral=True,
        )

    @app_commands.command(name="업데이트상태", description="최근 자동 업데이트 결과를 확인합니다. (봇 소유자 전용)")
    async def update_status(self, interaction: discord.Interaction):
        if not is_bot_owner(interaction.user):
            await interaction.response.send_message("이 명령어는 봇 소유자만 사용할 수 있습니다.", ephemeral=True)
            return
        try:
            status = UPDATE_STATUS.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            status = "아직 자동 업데이트 기록이 없습니다."
        except OSError:
            status = "업데이트 기록을 읽지 못했습니다."
        await interaction.response.send_message(f"```text\n{status[-1500:]}\n```", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Updater(bot))
