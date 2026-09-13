"""운영진용 기본 관리 명령어 Cog.

경고 이력은 DB에 남기고, 추방/차단/타임아웃은 디스코드 자체 감사 로그에 맡깁니다.
모든 명령어는 해당 권한이 있는 사람만 쓸 수 있도록 권한 체크를 걸어 둡니다.
"""
import logging
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

import config
import db

log = logging.getLogger("honor-chairman-bot.moderation")


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _log(self, guild: discord.Guild, text: str) -> None:
        if not config.MOD_LOG_CHANNEL_ID:
            return
        channel = guild.get_channel(config.MOD_LOG_CHANNEL_ID)
        if channel is None:
            return
        try:
            await channel.send(text)
        except discord.Forbidden:
            log.warning("운영 로그 채널에 보낼 권한이 없습니다: #%s", getattr(channel, "name", channel))

    @app_commands.command(name="kick", description="멤버를 서버에서 추방합니다.")
    @app_commands.describe(member="추방할 멤버", reason="사유")
    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.checks.bot_has_permissions(kick_members=True)
    async def kick(
        self, interaction: discord.Interaction, member: discord.Member, reason: str = "사유 없음"
    ) -> None:
        await member.kick(reason=f"{interaction.user}: {reason}")
        await interaction.response.send_message(f"👢 {member.mention}님을 추방했습니다. 사유: {reason}")
        await self._log(interaction.guild, f"👢 {interaction.user}가 {member}를 추방함 (사유: {reason})")

    @app_commands.command(name="ban", description="멤버를 서버에서 차단합니다.")
    @app_commands.describe(member="차단할 멤버", reason="사유")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.checks.bot_has_permissions(ban_members=True)
    async def ban(
        self, interaction: discord.Interaction, member: discord.Member, reason: str = "사유 없음"
    ) -> None:
        await member.ban(reason=f"{interaction.user}: {reason}")
        await interaction.response.send_message(f"🔨 {member.mention}님을 차단했습니다. 사유: {reason}")
        await self._log(interaction.guild, f"🔨 {interaction.user}가 {member}를 차단함 (사유: {reason})")

    @app_commands.command(name="timeout", description="멤버를 일정 시간 동안 타임아웃시킵니다.")
    @app_commands.describe(member="대상 멤버", minutes="타임아웃 시간(분, 최대 28일)", reason="사유")
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.checks.bot_has_permissions(moderate_members=True)
    async def timeout(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        minutes: app_commands.Range[int, 1, 40320],
        reason: str = "사유 없음",
    ) -> None:
        until = discord.utils.utcnow() + timedelta(minutes=minutes)
        await member.timeout(until, reason=f"{interaction.user}: {reason}")
        await interaction.response.send_message(
            f"🔇 {member.mention}님을 {minutes}분 동안 타임아웃했습니다. 사유: {reason}"
        )
        await self._log(
            interaction.guild, f"🔇 {interaction.user}가 {member}를 {minutes}분 타임아웃함 (사유: {reason})"
        )

    @app_commands.command(name="warn", description="멤버에게 경고를 기록합니다.")
    @app_commands.describe(member="대상 멤버", reason="사유")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str) -> None:
        await db.add_warning(interaction.guild_id, member.id, interaction.user.id, reason)
        count = len(await db.get_warnings(interaction.guild_id, member.id))
        await interaction.response.send_message(
            f"⚠️ {member.mention}님에게 경고를 기록했습니다. (누적 {count}회) 사유: {reason}"
        )
        await self._log(
            interaction.guild, f"⚠️ {interaction.user}가 {member}에게 경고함 (누적 {count}회, 사유: {reason})"
        )

    @app_commands.command(name="warnings", description="멤버의 경고 이력을 확인합니다.")
    @app_commands.describe(member="대상 멤버")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warnings(self, interaction: discord.Interaction, member: discord.Member) -> None:
        rows = await db.get_warnings(interaction.guild_id, member.id)
        if not rows:
            await interaction.response.send_message(f"{member.mention}님은 경고 이력이 없습니다.")
            return
        lines = [
            f"<t:{int(created_at)}:short> · <@{moderator_id}> · {reason}"
            for moderator_id, reason, created_at in rows[:20]
        ]
        embed = discord.Embed(
            title=f"{member.display_name}님의 경고 이력 ({len(rows)}건)",
            description="\n".join(lines),
            colour=discord.Colour.orange(),
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="clear", description="최근 메시지를 한꺼번에 삭제합니다.")
    @app_commands.describe(amount="삭제할 개수(1~100)")
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.checks.bot_has_permissions(manage_messages=True)
    async def clear(
        self, interaction: discord.Interaction, amount: app_commands.Range[int, 1, 100]
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"🧹 메시지 {len(deleted)}개를 삭제했습니다.", ephemeral=True)

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("이 명령어를 사용할 권한이 없습니다.", ephemeral=True)
            return
        if isinstance(error, app_commands.BotMissingPermissions):
            await interaction.response.send_message(
                "봇에게 필요한 권한이 없습니다. 서버 설정에서 봇 권한을 확인해주세요.", ephemeral=True
            )
            return
        log.exception("명령어 처리 중 오류", exc_info=error)
        if interaction.response.is_done():
            await interaction.followup.send("명령어 처리 중 오류가 발생했습니다.", ephemeral=True)
        else:
            await interaction.response.send_message("명령어 처리 중 오류가 발생했습니다.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Moderation(bot))
