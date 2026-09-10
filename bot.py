"""명예회장봇 상시 실행 진입점.

기존 `food_bot.py`는 GitHub Actions가 하루 한 번 켜서 메시지만 보내고 껐지만,
경험치·레벨·칭호·음성 채널 음악 시스템은 실시간 연결이 필요하므로
24시간 켜져 있는 이 진입점을 사용합니다.

실행:  DISCORD_TOKEN=... python bot.py
"""
import asyncio
import logging
import sys

import discord
from discord.ext import commands

import config
import db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("honorary-bot")

COGS = (
    "cogs.leveling",
    "cogs.titles",
    "cogs.menu",
    "cogs.traffic",
    "cogs.music",
    "cogs.tts",
    "cogs.help",
)


class HonoraryBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        # 역할 지급/회수와 랭킹 표시에 멤버 정보가 필요합니다. (특권 인텐트)
        intents.members = True
        # 통화방 참여 감지와 음성 채널 음악 재생에 필요합니다.
        intents.voice_states = True
        # 명령어는 전부 슬래시 명령어라 message_content 인텐트는 필요 없습니다.
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)
        self._synced = False

    async def setup_hook(self):
        for cog in COGS:
            await self.load_extension(cog)
            log.info("%s 로드 완료", cog)

        if config.GUILD_ID:
            await self._sync_to(discord.Object(id=config.GUILD_ID), str(config.GUILD_ID))
            self._synced = True
        # GUILD_ID가 없으면 아직 참여 중인 서버를 알 수 없으므로 on_ready에서 처리합니다.

    async def _sync_to(self, guild: discord.abc.Snowflake, label: str) -> None:
        """서버 단위로 슬래시 명령어를 등록합니다.

        전역(global) 등록은 디스코드 반영까지 최대 1시간이 걸리고 그동안 일부만
        보이기 때문에, 참여 중인 서버에 직접 등록해 즉시 반영되게 합니다.
        """
        try:
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
        except discord.Forbidden:
            log.error(
                "[%s] 명령어를 등록할 권한이 없습니다. 봇을 'applications.commands' "
                "스코프를 포함해 다시 초대하세요.", label,
            )
            return
        except discord.HTTPException as exc:
            log.error("[%s] 명령어 동기화 실패: %s", label, exc)
            return

        names = ", ".join(f"/{c.name}" for c in synced)
        log.info("[%s] 슬래시 명령어 %d개 동기화 → %s", label, len(synced), names)

    async def on_ready(self):
        log.info("%s 로그인 완료 (서버 %d개)", self.user, len(self.guilds))

        if not self._synced:
            self._synced = True  # on_ready는 재접속 때마다 다시 불립니다
            if not self.guilds:
                log.warning("참여 중인 서버가 없어 명령어를 등록하지 못했습니다.")
            for guild in self.guilds:
                await self._sync_to(guild, guild.name)

        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching, name="사우님들의 활동"
            )
        )

    async def on_guild_join(self, guild: discord.Guild):
        """새로 초대된 서버에도 즉시 명령어를 등록합니다."""
        await self._sync_to(guild, guild.name)


async def main():
    if not config.TOKEN:
        sys.exit(
            "DISCORD_TOKEN 환경변수가 없습니다.\n"
            "  예) export DISCORD_TOKEN='봇토큰'  또는 .env 파일 사용"
        )

    db.init(config.DB_PATH)
    log.info("데이터베이스 준비 완료: %s", config.DB_PATH)

    bot = HonoraryBot()
    try:
        await bot.start(config.TOKEN)
    finally:
        await bot.close()
        db.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("종료합니다.")
