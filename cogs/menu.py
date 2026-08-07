"""식단 자동 알림 Cog.

`bot.py`가 상시 켜져 있는 동안 매분 KST 시각을 확인하다가 `config.MENU_HOUR_KST`
시(時)가 되면 그날 처음 한 번만 `config.MENU_CHANNEL_ID` 채널에 식단을 올립니다.
크롤링·임베드 생성 로직은 `food_bot.py`(GitHub Actions 단발 실행)와 공유하도록
`menu_source`에 모아뒀으므로 여기서는 "언제 보낼지"만 관리합니다.
"""
import logging
from datetime import date, datetime

from discord.ext import commands, tasks

import config
import menu_source

log = logging.getLogger("honor-chairman-bot.menu")


class Menu(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # 같은 시간대에 여러 번 겹쳐 보내지 않도록 마지막으로 보낸 날짜를 기억합니다.
        self._last_sent: date | None = None
        if config.ENABLE_MENU_TASK:
            self.check_menu_time.start()

    def cog_unload(self) -> None:
        self.check_menu_time.cancel()

    @tasks.loop(minutes=1)
    async def check_menu_time(self) -> None:
        now = datetime.now(menu_source.KST)
        if now.hour != config.MENU_HOUR_KST or self._last_sent == now.date():
            return

        if not config.MENU_CHANNEL_ID:
            log.error("MENU_CHANNEL_ID가 설정되지 않아 식단을 보낼 수 없습니다.")
            return

        channel = self.bot.get_channel(
            config.MENU_CHANNEL_ID
        ) or await self.bot.fetch_channel(config.MENU_CHANNEL_ID)
        try:
            await channel.send(embed=await menu_source.build_embed())
        except Exception:
            log.exception("식단 전송 실패")
            return

        # 전송이 성공했을 때만 기록해야, 실패 시 다음 분에 재시도합니다.
        self._last_sent = now.date()
        log.info("식단 전송 완료 → #%s", getattr(channel, "name", channel.id))

    @check_menu_time.before_loop
    async def before_check_menu_time(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Menu(bot))
