"""칭호 시스템.

칭호는 곧 디스코드 역할입니다. 칭호를 만들면 서버에 역할이 자동 생성되고,
삭제하면 역할도 함께 사라집니다. 요구 레벨이 높은 칭호일수록 역할 목록
상단에 오도록 순서가 자동 정렬됩니다.
"""
import logging

import discord
from discord import app_commands
from discord.ext import commands

import config
import db

log = logging.getLogger(__name__)


def parse_colour(value: str | None) -> discord.Colour:
    """'#FFAA00' 또는 'FFAA00' 형식의 문자열을 색상으로 변환합니다."""
    if not value:
        return discord.Colour.default()
    try:
        return discord.Colour(int(value.lstrip("#"), 16))
    except ValueError:
        return discord.Colour.default()


@app_commands.guild_only()
class Titles(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── 내부 로직 ─────────────────────────────────────

    async def sync_member(self, member: discord.Member, level: int | None = None) -> None:
        """멤버의 레벨에 맞는 칭호만 남기고 나머지는 회수합니다."""
        if member.bot:
            return

        guild = member.guild
        titles = db.get_titles(guild.id)
        if not titles:
            return

        if level is None:
            level = db.get_user(guild.id, member.id)["level"]

        earned = [t for t in titles if level >= t["level"]]
        if config.KEEP_ONLY_HIGHEST_TITLE:
            # 요구 레벨 오름차순이므로 마지막 항목이 가장 높은 등급입니다.
            keep = {earned[-1]["role_id"]} if earned else set()
        else:
            keep = {t["role_id"] for t in earned}

        managed_ids = {t["role_id"] for t in titles}
        current = {r.id for r in member.roles} & managed_ids

        to_add = self._resolve(guild, keep - current)
        to_remove = self._resolve(guild, current - keep)

        try:
            if to_add:
                await member.add_roles(*to_add, reason="레벨에 따른 칭호 자동 지급")
            if to_remove:
                await member.remove_roles(*to_remove, reason="레벨에 따른 칭호 자동 회수")
        except discord.Forbidden:
            log.warning(
                "칭호를 조정할 권한이 없습니다. 봇 역할이 칭호 역할보다 위에 있는지 "
                "확인하세요. (서버: %s, 멤버: %s)", guild.id, member.id,
            )

    def _resolve(self, guild: discord.Guild, role_ids: set[int]) -> list[discord.Role]:
        """봇이 실제로 부여/회수할 수 있는 역할만 남깁니다."""
        resolved = []
        for role_id in role_ids:
            role = guild.get_role(role_id)
            # 봇보다 위에 있는 역할은 건드릴 수 없습니다.
            if role is not None and role < guild.me.top_role:
                resolved.append(role)
        return resolved

    async def reorder(self, guild: discord.Guild) -> None:
        """요구 레벨이 높은 칭호일수록 역할 목록 위쪽에 오도록 정렬합니다."""
        levels_by_role = {t["role_id"]: t["level"] for t in db.get_titles(guild.id)}
        roles = self._resolve(guild, set(levels_by_role))
        if not roles:
            return

        roles.sort(key=lambda r: levels_by_role[r.id])  # 낮은 레벨이 아래로

        # 봇 역할 바로 아래 구간에 차곡차곡 쌓습니다. @everyone(0) 위여야 하므로 최소 1.
        base = max(1, guild.me.top_role.position - len(roles))
        positions = {role: base + idx for idx, role in enumerate(roles)}

        try:
            await guild.edit_role_positions(positions=positions, reason="칭호 등급 정렬")
        except discord.Forbidden:
            log.warning("역할 순서를 변경할 권한이 없습니다. (서버: %s)", guild.id)
        except discord.HTTPException as exc:
            log.warning("역할 순서 변경 실패: %s", exc)

    # ── 명령어 ────────────────────────────────────────

    @app_commands.command(name="칭호추가", description="칭호를 만들고 서버 역할로 자동 등록합니다.")
    @app_commands.describe(
        이름="칭호 이름 (역할 이름으로 그대로 사용됩니다)",
        레벨="이 칭호를 획득하는 데 필요한 레벨",
        색상="역할 색상 (예: #E74C3C). 생략하면 기본색",
    )
    @app_commands.checks.has_permissions(manage_roles=True)
    async def add_title(
        self,
        interaction: discord.Interaction,
        이름: str,
        레벨: app_commands.Range[int, 0, 1000],
        색상: str | None = None,
    ):
        guild = interaction.guild
        if db.find_title_by_name(guild.id, 이름) is not None:
            await interaction.response.send_message(
                f"이미 `{이름}` 칭호가 있습니다.", ephemeral=True
            )
            return

        await interaction.response.defer()
        try:
            role = await guild.create_role(
                name=이름,
                colour=parse_colour(색상),
                hoist=True,  # 멤버 목록에서 칭호별로 구분되어 표시됩니다
                reason=f"{interaction.user}님이 칭호 추가",
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "역할을 만들 권한이 없습니다. 봇에게 `역할 관리` 권한을 주세요.",
                ephemeral=True,
            )
            return

        db.add_title(guild.id, role.id, 이름, 레벨)
        await self.reorder(guild)

        embed = discord.Embed(
            title="✅ 칭호가 추가되었습니다",
            description=f"{role.mention} · 필요 레벨 **{레벨}**",
            colour=role.colour,
        )
        embed.set_footer(text="/칭호동기화 를 실행하면 기존 멤버에게도 즉시 반영됩니다.")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="칭호삭제", description="칭호와 해당 역할을 함께 삭제합니다.")
    @app_commands.describe(이름="삭제할 칭호 이름")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def remove_title(self, interaction: discord.Interaction, 이름: str):
        guild = interaction.guild
        title = db.find_title_by_name(guild.id, 이름)
        if title is None:
            await interaction.response.send_message(
                f"`{이름}` 칭호를 찾을 수 없습니다.", ephemeral=True
            )
            return

        await interaction.response.defer()
        role = guild.get_role(title["role_id"])
        if role is not None:
            try:
                await role.delete(reason=f"{interaction.user}님이 칭호 삭제")
            except discord.Forbidden:
                await interaction.followup.send(
                    "역할을 삭제할 권한이 없습니다.", ephemeral=True
                )
                return

        db.delete_title(guild.id, title["role_id"])
        await self.reorder(guild)
        await interaction.followup.send(f"🗑️ `{이름}` 칭호를 삭제했습니다.")

    @remove_title.autocomplete("이름")
    async def title_autocomplete(self, interaction: discord.Interaction, current: str):
        titles = db.get_titles(interaction.guild.id)
        return [
            app_commands.Choice(name=f"{t['name']} (Lv.{t['level']})", value=t["name"])
            for t in titles
            if current.lower() in t["name"].lower()
        ][:25]

    @app_commands.command(name="칭호목록", description="등록된 칭호를 등급 순으로 보여줍니다.")
    async def list_titles(self, interaction: discord.Interaction):
        titles = db.get_titles(interaction.guild.id)
        if not titles:
            await interaction.response.send_message(
                "아직 등록된 칭호가 없습니다. `/칭호추가` 로 만들어 보세요.", ephemeral=True
            )
            return

        lines = []
        for t in reversed(titles):  # 높은 등급이 위로
            role = interaction.guild.get_role(t["role_id"])
            label = role.mention if role else f"~~{t['name']}~~ (역할 없음)"
            lines.append(f"**Lv.{t['level']}** — {label}")

        embed = discord.Embed(
            title="🏅 칭호 목록",
            description="\n".join(lines),
            colour=discord.Colour.gold(),
        )
        mode = "최고 등급 1개만 유지" if config.KEEP_ONLY_HIGHEST_TITLE else "획득한 칭호 모두 유지"
        embed.set_footer(text=f"지급 방식: {mode}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="칭호동기화", description="서버 전체 멤버의 칭호를 현재 레벨에 맞게 다시 계산합니다."
    )
    @app_commands.checks.has_permissions(manage_roles=True)
    async def resync(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild

        await self.reorder(guild)
        count = 0
        for member in guild.members:
            if member.bot:
                continue
            await self.sync_member(member)
            count += 1

        await interaction.followup.send(f"✅ 멤버 {count}명의 칭호를 동기화했습니다.", ephemeral=True)

    # ── 정리 ──────────────────────────────────────────

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        """관리자가 역할을 직접 지운 경우 칭호 등록도 함께 정리합니다."""
        db.delete_title(role.guild.id, role.id)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """재입장한 멤버에게 기존 레벨에 맞는 칭호를 다시 지급합니다."""
        await self.sync_member(member)

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        from cogs.leveling import handle_command_error

        await handle_command_error(interaction, error)


async def setup(bot: commands.Bot):
    await bot.add_cog(Titles(bot))
