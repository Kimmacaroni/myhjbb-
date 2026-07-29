"""명예회장봇 상시 실행 진입점.

기존 `food_bot.py`는 GitHub Actions가 하루 한 번 켜서 메시지만 보내고 껐지만,
경험치·레벨·칭호 시스템은 채팅과 통화방을 실시간으로 지켜봐야 하므로
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

COGS = ("cogs.leveling", "cogs.titles", "cogs.menu")


class HonoraryBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        # 역할 지급/회수와 랭킹 표시에 멤버 정보가 필요합니다. (특권 인텐트)
        intents.members = True
        # 통화방 참여 감지에 필요합니다.
        intents.voice_states = True
        # 명령어는 전부 슬래시 명령어라 message_content 인텐트는 필요 없습니다.
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)

    async def setup_hook(self):
        for cog in COGS:
            await self.load_extension(cog)
            log.info("%s 로드 완료", cog)

        if config.GUILD_ID:
            # 특정 서버에만 등록하면 명령어가 즉시 반영됩니다.
            guild = discord.Object(id=config.GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
        else:
            # 전역 등록은 디스코드 반영까지 최대 1시간이 걸립니다.
            synced = await self.tree.sync()
        log.info("슬래시 명령어 %d개 동기화", len(synced))

    async def on_ready(self):
        log.info("%s 로그인 완료 (서버 %d개)", self.user, len(self.guilds))
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching, name="사우님들의 활동"
            )
        )


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
