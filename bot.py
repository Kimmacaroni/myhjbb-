"""명예회장봇 v2 상시 실행 진입점.

식단 자동 알림처럼 매분 시각을 지켜봐야 하는 기능이나, 채팅/통화 경험치처럼
계속 이벤트를 지켜봐야 하는 기능은 GitHub Actions 단발 실행(`food_bot.py`)으로는
만들 수 없습니다. 이 파일을 호스팅 환경(서버, 컨테이너 등)에 올려 계속 켜두면,
아래 Cog들이 알아서 동작합니다.

    cogs/menu.py        정해진 시각에 식단 자동 전송
    cogs/leveling.py     채팅/통화 경험치, 레벨업, 레벨 역할 지급
    cogs/moderation.py   추방/차단/타임아웃/경고/메시지 삭제
    cogs/welcome.py      신규 멤버 환영 메시지
    cogs/utility.py      서버/유저 정보, 도움말

필요한 환경변수는 config.py에 정리되어 있습니다. 필수는 DISCORD_TOKEN뿐이고,
나머지는 해당 기능을 켜고 싶을 때만 채우면 됩니다.

디스코드 개발자 포털 > Bot > Privileged Gateway Intents 에서
"SERVER MEMBERS INTENT"를 켜야 환영 메시지·레벨 역할 지급이 정상 동작합니다.
"""
import asyncio
import logging

import discord
from discord.ext import commands

import config
import db

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("honor-chairman-bot")

INITIAL_EXTENSIONS = [
    "cogs.menu",
    "cogs.leveling",
    "cogs.moderation",
    "cogs.welcome",
    "cogs.utility",
]


class HonorChairmanBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        # 신규 멤버 감지·역할 지급·통화방 인원 확인에 필요합니다(포털에서 별도로 켜야 함).
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self) -> None:
        await db.init()
        for extension in INITIAL_EXTENSIONS:
            await self.load_extension(extension)

        if config.GUILD_ID:
            # 특정 서버에만 등록하면 반영이 즉시 됩니다(전역 등록은 최대 1시간).
            guild = discord.Object(id=config.GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()


async def run() -> None:
    bot = HonorChairmanBot()

    @bot.event
    async def on_ready():
        log.info("로그인 완료: %s (id=%s)", bot.user, bot.user.id)

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
