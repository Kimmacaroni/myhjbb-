"""채팅/통화 경험치, 레벨업, 레벨 역할 지급을 담당하는 Cog.

- 채팅: 메시지를 보낼 때마다(쿨다운 있음) 무작위 경험치를 줍니다.
- 통화: 통화방에 일정 인원 이상 모여 있으면 분당 경험치를 줍니다.
레벨이 오르면 config.LEVEL_ROLES에 등록된 역할을 지급하고, KEEP_ONLY_HIGHEST_TITLE이
켜져 있으면 그보다 낮은 레벨의 역할은 회수합니다.
"""
import logging
import random
import time

import discord
from discord import app_commands
from discord.ext import commands, tasks

import config
import db

log = logging.getLogger("honor-chairman-bot.leveling")


class Leveling(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # 채팅 쿨다운은 재시작되면 리셋돼도 무방한 짧은 값이라 DB 대신 메모리에 둡니다.
        self._chat_cooldowns: dict[tuple[int, int], float] = {}
        self.voice_xp_tick.start()

    def cog_unload(self) -> None:
        self.voice_xp_tick.cancel()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is None:
            return

        key = (message.guild.id, message.author.id)
        now = time.monotonic()
        last = self._chat_cooldowns.get(key, 0.0)
        if now - last < config.CHAT_XP_COOLDOWN:
            return
        self._chat_cooldowns[key] = now

        amount = random.randint(config.CHAT_XP_MIN, config.CHAT_XP_MAX)
        await self._grant_xp(message.guild, message.author, amount, message.channel)

    @tasks.loop(minutes=1)
    async def voice_xp_tick(self) -> None:
        for guild in self.bot.guilds:
            for channel in guild.voice_channels:
                if channel == guild.afk_channel:
                    continue
                members = [m for m in channel.members if not m.bot]
                if len(members) < config.VOICE_MIN_MEMBERS:
                    continue
                for member in members:
                    if (
                        config.VOICE_IGNORE_SELF_MUTED
                        and member.voice
                        and member.voice.self_mute
                    ):
                        continue
                    await self._grant_xp(guild, member, config.VOICE_XP_PER_MINUTE, None)

    @voice_xp_tick.before_loop
    async def before_voice_xp_tick(self) -> None:
        await self.bot.wait_until_ready()

    async def _grant_xp(
        self,
        guild: discord.Guild,
        member: discord.Member,
        amount: int,
        announce_channel: discord.abc.Messageable | None,
    ) -> None:
        _, new_level, old_level = await db.add_xp(guild.id, member.id, amount)
        if new_level <= old_level:
            return

        await self._apply_level_roles(guild, member, new_level)

        channel = announce_channel
        if config.LEVEL_UP_CHANNEL_ID:
            channel = guild.get_channel(config.LEVEL_UP_CHANNEL_ID) or channel
        if channel is None:
            return
        try:
            await channel.send(f"🎉 {member.mention}님이 **레벨 {new_level}**(으)로 올랐습니다!")
        except discord.Forbidden:
            log.warning("레벨업 메시지를 보낼 권한이 없습니다: #%s", getattr(channel, "name", channel))

    async def _apply_level_roles(
        self, guild: discord.Guild, member: discord.Member, new_level: int
    ) -> None:
        if not config.LEVEL_ROLES:
            return

        earned_levels = sorted(lv for lv in config.LEVEL_ROLES if lv <= new_level)
        if not earned_levels:
            return

        if config.KEEP_ONLY_HIGHEST_TITLE:
            keep_id = config.LEVEL_ROLES[earned_levels[-1]]
            add_ids = {keep_id}
            remove_ids = {rid for rid in config.LEVEL_ROLES.values() if rid != keep_id}
        else:
            add_ids = {config.LEVEL_ROLES[lv] for lv in earned_levels}
            remove_ids = set()

        try:
            if remove_ids:
                roles_to_remove = [
                    role
                    for rid in remove_ids
                    if (role := guild.get_role(rid)) and role in member.roles
                ]
                if roles_to_remove:
                    await member.remove_roles(*roles_to_remove, reason="레벨 칭호 갱신")

            roles_to_add = [
                role
                for rid in add_ids
                if (role := guild.get_role(rid)) and role not in member.roles
            ]
            if roles_to_add:
                await member.add_roles(*roles_to_add, reason="레벨업 보상")
        except discord.Forbidden:
            log.warning("역할을 지급/회수할 권한이 없습니다 (guild=%s, member=%s)", guild.id, member.id)

    @app_commands.command(name="level", description="자신 또는 다른 사람의 레벨과 경험치를 확인합니다.")
    @app_commands.describe(member="확인할 멤버 (비우면 자기 자신)")
    async def level(
        self, interaction: discord.Interaction, member: discord.Member | None = None
    ) -> None:
        target = member or interaction.user
        xp, level = await db.get_member(interaction.guild_id, target.id)
        curr_level_xp = db.xp_for_level(level)
        next_level_xp = db.xp_for_level(level + 1)
        embed = discord.Embed(
            title=f"{target.display_name}님의 레벨",
            description=(
                f"레벨 **{level}** · 경험치 {xp} "
                f"({xp - curr_level_xp}/{next_level_xp - curr_level_xp})"
            ),
            colour=discord.Colour.blurple(),
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="서버 경험치 순위를 보여줍니다.")
    async def leaderboard(self, interaction: discord.Interaction) -> None:
        rows = await db.get_leaderboard(interaction.guild_id, limit=10)
        if not rows:
            await interaction.response.send_message("아직 기록된 경험치가 없습니다.")
            return

        lines = []
        for rank, (user_id, xp, level) in enumerate(rows, start=1):
            member = interaction.guild.get_member(user_id)
            name = member.display_name if member else f"(알 수 없음 {user_id})"
            lines.append(f"**{rank}.** {name} — 레벨 {level} ({xp} XP)")

        embed = discord.Embed(
            title="🏆 경험치 순위",
            description="\n".join(lines),
            colour=discord.Colour.gold(),
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Leveling(bot))
