"""신규 멤버 환영 메시지 Cog."""
import logging

import discord
from discord.ext import commands

import config

log = logging.getLogger("honor-chairman-bot.welcome")


class Welcome(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if not config.WELCOME_CHANNEL_ID:
            return
        channel = member.guild.get_channel(config.WELCOME_CHANNEL_ID)
        if channel is None:
            return

        embed = discord.Embed(
            title="👋 새로운 사우님이 오셨습니다!",
            description=f"{member.mention}님, {member.guild.name}에 오신 것을 환영합니다!",
            colour=discord.Colour.green(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            log.warning("환영 메시지를 보낼 권한이 없습니다: #%s", getattr(channel, "name", channel))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Welcome(bot))
