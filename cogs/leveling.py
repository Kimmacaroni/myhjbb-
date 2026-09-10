"""경험치 · 레벨 시스템.

채팅과 통화방 참여도에 따라 경험치를 지급하고, 누적 경험치가 기준을 넘으면
레벨이 오릅니다. 레벨이 바뀌면 칭호 시스템에 반영을 요청합니다.
"""
import logging
import random
import re
import time

import discord
from discord import app_commands
from discord.ext import commands, tasks

import config
import db
import levels
from access_control import admin_only

log = logging.getLogger(__name__)

# 자릿수를 실제 스노우플레이크 길이(17~19자리)로 엄격히 제한하지 않습니다 —
# 잘못된 ID는 어차피 resolve_member()의 서버 조회에서 걸러지므로, 여기서는
# "숫자로만 이루어졌는지"만 확인합니다.
_MENTION_RE = re.compile(r"^<@!?(\d{1,20})>$")
_ID_RE = re.compile(r"^\d{1,20}$")

_MEMBER_RESOLVE_FAILED = (
    "유저를 멘션(@닉네임)하거나 유저 ID를 입력해 주세요. (이 서버에 없는 유저일 수도 있습니다)"
)


async def resolve_member(guild: discord.Guild, raw: str) -> discord.Member | None:
    """멘션(`<@id>`) 또는 순수 ID 텍스트에서 서버 멤버를 찾습니다.

    디스코드 기본 유저 선택 옵션(discord.Member 타입)을 쓰지 않는 이유:
    그 선택 목록은 명령어를 입력하는 채널을 볼 수 있는 사람만 후보로
    보여주는 디스코드 클라이언트 제약이 있습니다. 관리자 전용 채널에서
    일반 멤버를 대상으로 지정해야 하는 경우 후보에 아예 뜨지 않으므로,
    대신 멘션/ID를 텍스트로 받아 여기서 직접 파싱합니다.
    """
    raw = raw.strip()
    match = _MENTION_RE.match(raw)
    user_id = int(match.group(1)) if match else (int(raw) if _ID_RE.match(raw) else None)
    if user_id is None:
        return None

    member = guild.get_member(user_id)
    if member is not None:
        return member
    try:
        return await guild.fetch_member(user_id)
    except discord.NotFound:
        return None


@app_commands.guild_only()
class Leveling(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # (guild_id, user_id) -> 마지막으로 채팅 경험치를 받은 시각
        self._chat_cooldown: dict[tuple[int, int], float] = {}

    async def cog_load(self):
        self.voice_xp_tick.start()

    async def cog_unload(self):
        self.voice_xp_tick.cancel()

    # ── 경험치 지급 ───────────────────────────────────

    async def grant(
        self,
        member: discord.Member,
        amount: int,
        *,
        channel: discord.abc.Messageable | None = None,
        voice_minutes: int = 0,
        messages: int = 0,
        announce: bool = True,
    ) -> tuple[int, int]:
        """경험치를 지급/차감하고 레벨 변동을 처리합니다.

        Returns:
            (변경 전 레벨, 변경 후 레벨)
        """
        before, after, _ = db.add_xp(
            member.guild.id, member.id, amount,
            voice_minutes=voice_minutes, messages=messages,
        )

        if before != after:
            titles = self.bot.get_cog("Titles")
            if titles is not None:
                await titles.sync_member(member, after)
            if announce and after > before:
                await self._announce_level_up(member, after, channel)

        return before, after

    async def _announce_level_up(
        self,
        member: discord.Member,
        level: int,
        channel: discord.abc.Messageable | None,
    ) -> None:
        target = self._announce_channel(member.guild, channel)
        if target is None:
            return

        embed = discord.Embed(
            title="🎉 레벨 업!",
            description=f"{member.mention} 님이 **레벨 {level}** 이(가) 되었습니다.",
            colour=discord.Colour.green(),
        )

        # 이번 레벨업으로 새로 얻은 칭호가 있으면 함께 알려줍니다.
        earned = [t for t in db.get_titles(member.guild.id) if t["level"] == level]
        if earned:
            names = ", ".join(f"**{t['name']}**" for t in earned)
            embed.add_field(name="새로운 칭호", value=names, inline=False)

        try:
            await target.send(embed=embed)
        except discord.Forbidden:
            log.warning("레벨업 알림을 보낼 권한이 없습니다. (서버: %s)", member.guild.id)

    def _announce_channel(
        self, guild: discord.Guild, fallback: discord.abc.Messageable | None
    ):
        if config.LEVEL_UP_CHANNEL_ID:
            channel = guild.get_channel(config.LEVEL_UP_CHANNEL_ID)
            if channel is not None:
                return channel
        return fallback or guild.system_channel

    # ── 채팅 경험치 ───────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return

        key = (message.guild.id, message.author.id)
        now = time.monotonic()
        if now - self._chat_cooldown.get(key, 0.0) < config.CHAT_XP_COOLDOWN:
            return
        self._chat_cooldown[key] = now

        amount = random.randint(config.CHAT_XP_MIN, config.CHAT_XP_MAX)
        await self.grant(message.author, amount, channel=message.channel, messages=1)

    # ── 통화방 경험치 ─────────────────────────────────

    @tasks.loop(minutes=1)
    async def voice_xp_tick(self):
        """1분마다 통화방에 있는 멤버에게 경험치를 지급합니다.

        입·퇴장 이벤트 대신 주기적으로 현재 상태를 확인하는 방식이라, 봇이
        재시작되어도 통화 중인 사람의 경험치가 누락되지 않습니다.
        """
        for guild in self.bot.guilds:
            for channel in guild.voice_channels:
                if guild.afk_channel is not None and channel.id == guild.afk_channel.id:
                    continue

                humans = [m for m in channel.members if not m.bot]
                if len(humans) < config.VOICE_MIN_MEMBERS:
                    continue

                for member in humans:
                    state = member.voice
                    if state is None:
                        continue
                    if config.VOICE_IGNORE_SELF_MUTED and (state.self_mute or state.self_deaf):
                        continue
                    await self.grant(
                        member, config.VOICE_XP_PER_MINUTE, voice_minutes=1
                    )

    @voice_xp_tick.before_loop
    async def before_voice_tick(self):
        await self.bot.wait_until_ready()

    @voice_xp_tick.error
    async def voice_tick_error(self, exc: BaseException):
        log.exception("통화방 경험치 지급 중 오류", exc_info=exc)

    # ── 조회 명령어 ───────────────────────────────────

    @app_commands.command(name="경험치", description="내 경험치와 레벨을 확인합니다.")
    @app_commands.describe(유저="확인할 대상 — 멘션(@닉네임) 또는 유저 ID (생략하면 본인)")
    @admin_only()
    async def show_xp(self, interaction: discord.Interaction, 유저: str | None = None):
        if 유저 is None:
            member = interaction.user
        else:
            member = await resolve_member(interaction.guild, 유저)
            if member is None:
                await interaction.response.send_message(_MEMBER_RESOLVE_FAILED, ephemeral=True)
                return
        row = db.get_user(interaction.guild.id, member.id)
        level, earned, needed = levels.progress(row["xp"])
        rank = db.rank_of(interaction.guild.id, member.id)

        embed = discord.Embed(
            title=f"{member.display_name} 님의 활동 기록",
            colour=member.colour,
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="레벨", value=f"**{level}**")
        embed.add_field(name="누적 경험치", value=f"{row['xp']:,}")
        embed.add_field(name="순위", value=f"{rank}위" if rank else "—")
        embed.add_field(
            name=f"다음 레벨까지 ({earned:,} / {needed:,})",
            value=levels.progress_bar(earned, needed),
            inline=False,
        )

        current = [t for t in db.get_titles(interaction.guild.id) if level >= t["level"]]
        embed.add_field(
            name="보유 칭호",
            value=current[-1]["name"] if current else "아직 없음",
            inline=False,
        )
        embed.set_footer(
            text=f"채팅 {row['messages']:,}회 · 통화 {row['voice_minutes']:,}분"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="랭킹", description="서버 경험치 순위를 보여줍니다.")
    @app_commands.describe(인원="표시할 인원 수 (기본 10명)")
    @admin_only()
    async def leaderboard(
        self,
        interaction: discord.Interaction,
        인원: app_commands.Range[int, 1, 25] = 10,
    ):
        rows = db.leaderboard(interaction.guild.id, 인원)
        if not rows:
            await interaction.response.send_message(
                "아직 경험치를 쌓은 사람이 없습니다.", ephemeral=True
            )
            return

        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        lines = []
        for idx, row in enumerate(rows, start=1):
            member = interaction.guild.get_member(row["user_id"])
            name = member.display_name if member else f"(퇴장한 유저 {row['user_id']})"
            prefix = medals.get(idx, f"`{idx}.`")
            lines.append(f"{prefix} **{name}** — Lv.{row['level']} ({row['xp']:,} XP)")

        embed = discord.Embed(
            title="📊 경험치 랭킹",
            description="\n".join(lines),
            colour=discord.Colour.blurple(),
        )
        await interaction.response.send_message(embed=embed)

    # ── 수동 조정 명령어 ──────────────────────────────

    @app_commands.command(name="경험치지급", description="지정한 멤버에게 경험치를 지급합니다.")
    @app_commands.describe(유저="지급 대상 — 멘션(@닉네임) 또는 유저 ID", 수량="지급할 경험치")
    @admin_only()
    async def give_xp(
        self,
        interaction: discord.Interaction,
        유저: str,
        수량: app_commands.Range[int, 1, 1_000_000],
    ):
        member = await resolve_member(interaction.guild, 유저)
        if member is None:
            await interaction.response.send_message(_MEMBER_RESOLVE_FAILED, ephemeral=True)
            return
        await self._adjust(interaction, member, 수량)

    @app_commands.command(name="경험치차감", description="지정한 멤버의 경험치를 차감합니다.")
    @app_commands.describe(유저="차감 대상 — 멘션(@닉네임) 또는 유저 ID", 수량="차감할 경험치")
    @admin_only()
    async def take_xp(
        self,
        interaction: discord.Interaction,
        유저: str,
        수량: app_commands.Range[int, 1, 1_000_000],
    ):
        member = await resolve_member(interaction.guild, 유저)
        if member is None:
            await interaction.response.send_message(_MEMBER_RESOLVE_FAILED, ephemeral=True)
            return
        await self._adjust(interaction, member, -수량)

    @app_commands.command(name="경험치설정", description="멤버의 경험치를 특정 값으로 맞춥니다.")
    @app_commands.describe(유저="대상 — 멘션(@닉네임) 또는 유저 ID", 수량="설정할 누적 경험치")
    @admin_only()
    async def set_xp(
        self,
        interaction: discord.Interaction,
        유저: str,
        수량: app_commands.Range[int, 0, 10_000_000],
    ):
        member = await resolve_member(interaction.guild, 유저)
        if member is None:
            await interaction.response.send_message(_MEMBER_RESOLVE_FAILED, ephemeral=True)
            return
        current = db.get_user(interaction.guild.id, member.id)["xp"]
        await self._adjust(interaction, member, 수량 - current)

    async def _adjust(
        self, interaction: discord.Interaction, member: discord.Member, delta: int
    ):
        if member.bot:
            await interaction.response.send_message(
                "봇에게는 경험치를 줄 수 없습니다.", ephemeral=True
            )
            return

        await interaction.response.defer()
        before, after = await self.grant(
            member, delta, channel=interaction.channel, announce=False
        )
        row = db.get_user(interaction.guild.id, member.id)

        verb = "지급" if delta >= 0 else "차감"
        embed = discord.Embed(
            title=f"경험치 {verb} 완료",
            description=(
                f"{member.mention} · **{abs(delta):,} XP** {verb}\n"
                f"누적 **{row['xp']:,} XP** · 레벨 **{before} → {after}**"
            ),
            colour=discord.Colour.green() if delta >= 0 else discord.Colour.red(),
        )
        embed.set_footer(text=f"실행: {interaction.user.display_name}")
        await interaction.followup.send(embed=embed)

    # ── 오류 처리 ─────────────────────────────────────

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        await handle_command_error(interaction, error)


PERMISSION_NAMES = {
    "manage_roles": "역할 관리",
    "manage_guild": "서버 관리",
    "administrator": "관리자",
}


async def handle_command_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
):
    if isinstance(error, app_commands.CheckFailure):
        message = "이 명령어는 서버 관리자만 사용할 수 있습니다."
    elif isinstance(error, app_commands.MissingPermissions):
        needed = ", ".join(
            f"`{PERMISSION_NAMES.get(p, p)}`" for p in error.missing_permissions
        )
        message = f"이 명령어는 {needed} 권한이 있는 사람만 사용할 수 있습니다."
    else:
        log.exception("명령어 처리 중 오류", exc_info=error)
        message = "명령어를 처리하는 중 문제가 생겼습니다. 로그를 확인해 주세요."

    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Leveling(bot))
