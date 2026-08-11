"""서버/유저 정보 조회 및 도움말 Cog."""
import discord
from discord import app_commands
from discord.ext import commands


class Utility(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="serverinfo", description="서버 정보를 보여줍니다.")
    async def serverinfo(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        embed = discord.Embed(title=guild.name, colour=discord.Colour.blurple())
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.add_field(name="멤버 수", value=str(guild.member_count))
        embed.add_field(name="개설일", value=discord.utils.format_dt(guild.created_at, style="D"))
        embed.add_field(name="서버장", value=str(guild.owner) if guild.owner else "알 수 없음")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="userinfo", description="유저 정보를 보여줍니다.")
    @app_commands.describe(member="확인할 멤버 (비우면 자기 자신)")
    async def userinfo(
        self, interaction: discord.Interaction, member: discord.Member | None = None
    ) -> None:
        target = member or interaction.user
        embed = discord.Embed(title=str(target), colour=discord.Colour.blurple())
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(
            name="가입일",
            value=discord.utils.format_dt(target.joined_at, style="D") if target.joined_at else "알 수 없음",
        )
        embed.add_field(name="계정 생성일", value=discord.utils.format_dt(target.created_at, style="D"))
        roles = [role.mention for role in reversed(target.roles) if role.name != "@everyone"]
        embed.add_field(name="역할", value=", ".join(roles) if roles else "없음", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="help", description="사용 가능한 명령어 목록을 보여줍니다.")
    async def help(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(title="🤖 명예회장봇 명령어", colour=discord.Colour.blurple())
        embed.add_field(
            name="레벨",
            value="`/level` 내 레벨 확인 · `/leaderboard` 순위 확인",
            inline=False,
        )
        embed.add_field(
            name="정보",
            value="`/serverinfo` 서버 정보 · `/userinfo` 유저 정보",
            inline=False,
        )
        embed.add_field(
            name="운영진 전용",
            value="`/kick` `/ban` `/timeout` `/warn` `/warnings` `/clear`",
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Utility(bot))
