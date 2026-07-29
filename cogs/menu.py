"""식단 브리핑.

기존 `food_bot.py`가 하던 일을 상시 실행 봇 안으로 옮긴 것입니다.
매일 정해진 시각(KST)에 식단표를 크롤링해 지정 채널로 보냅니다.
"""
import asyncio
import logging
from datetime import datetime, time, timedelta, timezone

import discord
import requests
from bs4 import BeautifulSoup
from discord import app_commands
from discord.ext import commands, tasks

import config

log = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))


def fetch_menu() -> str:
    """식단표 페이지를 읽어 텍스트로 정리합니다."""
    response = requests.get(
        config.MENU_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=10
    )
    response.encoding = "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")

    content = soup.find("div", class_="content") or soup.find("table")
    if content is None:
        raise ValueError("식단표 영역을 찾지 못했습니다.")

    lines = [line.strip() for line in content.get_text().split("\n") if line.strip()]
    if not lines:
        raise ValueError("식단표가 비어 있습니다.")

    final = []
    for line in lines:
        if any(word in line for word in ("중식", "석식")):
            final.append("─" * 20)
        final.append(line)
    return "\n".join(final)


@app_commands.guild_only()
class Menu(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        if config.ENABLE_MENU_TASK and config.MENU_CHANNEL_ID:
            self.daily_menu.change_interval(
                time=time(hour=config.MENU_HOUR_KST, tzinfo=KST)
            )
            self.daily_menu.start()
        else:
            log.info("식단 자동 전송이 꺼져 있습니다.")

    async def cog_unload(self):
        self.daily_menu.cancel()

    async def build_embed(self) -> discord.Embed:
        # requests는 동기 호출이라 이벤트 루프를 막지 않도록 스레드로 넘깁니다.
        menu = await asyncio.to_thread(fetch_menu)
        embed = discord.Embed(
            title="🏢 명예회장님의 오늘의 식단 브리핑",
            description=(
                f"**날짜: {datetime.now(KST).strftime('%Y년 %m월 %d일')}**\n\n{menu}"
            ),
            colour=15158332,
        )
        embed.set_footer(text="오늘도 안전 운행하십시오. 대원여객 파이팅!")
        return embed

    @tasks.loop(time=time(hour=6, tzinfo=KST))
    async def daily_menu(self):
        channel = self.bot.get_channel(config.MENU_CHANNEL_ID)
        if channel is None:
            log.warning("식단 채널(%s)을 찾을 수 없습니다.", config.MENU_CHANNEL_ID)
            return
        try:
            await channel.send(embed=await self.build_embed())
        except Exception:
            # 조용히 넘어가면 며칠 뒤에나 알게 되므로 로그에 확실히 남깁니다.
            log.exception("식단 전송 실패")

    @daily_menu.before_loop
    async def before_daily_menu(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="식단", description="오늘의 식단표를 지금 불러옵니다.")
    async def menu_now(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            await interaction.followup.send(embed=await self.build_embed())
        except Exception as exc:
            log.exception("식단 조회 실패")
            await interaction.followup.send(f"❌ 식단을 불러오지 못했습니다: {exc}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Menu(bot))
