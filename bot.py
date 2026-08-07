"""명예회장봇 v2 상시 실행 진입점.

식단 자동 알림처럼 매분 시각을 지켜봐야 하는 기능은 GitHub Actions 단발 실행
(`food_bot.py`)으로는 만들 수 없습니다. 이 파일을 호스팅 환경(서버, 컨테이너 등)에
올려 계속 켜두면, 정해진 시각에 `cogs/menu.py`가 알아서 식단을 올립니다.

필요한 환경변수 (config.py 참고):
    DISCORD_TOKEN     봇 토큰 (필수)
    MENU_CHANNEL_ID   식단을 올릴 채널 ID (필수)
    MENU_HOUR_KST     식단을 보낼 시각, KST 기준 (기본 6시)
    ENABLE_MENU_TASK  식단 자동 알림 켜짐/꺼짐 (기본 켜짐)
"""
import asyncio
import logging

import discord
from discord.ext import commands

import config

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("honor-chairman-bot")

INITIAL_EXTENSIONS = ["cogs.menu"]


def build_bot() -> commands.Bot:
    intents = discord.Intents.default()
    bot = commands.Bot(command_prefix="!", intents=intents)

    @bot.event
    async def on_ready():
        log.info("로그인 완료: %s (id=%s)", bot.user, bot.user.id)

    return bot


async def run() -> None:
    bot = build_bot()
    for extension in INITIAL_EXTENSIONS:
        await bot.load_extension(extension)

    async with bot:
        await bot.start(config.TOKEN)


def main() -> int:
    if not config.TOKEN:
        log.error("DISCORD_TOKEN이 없습니다. 환경변수로 등록하세요.")
        return 1

    try:
        asyncio.run(run())
    except discord.LoginFailure:
        log.error("토큰이 올바르지 않습니다. 토큰을 재발급해 등록하세요.")
        return 1
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
