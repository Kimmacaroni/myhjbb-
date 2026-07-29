"""식단 브리핑.

기존 `food_bot.py`가 하던 일을 상시 실행 봇 안으로 옮긴 것입니다.
매일 정해진 시각(KST)에 식단표를 크롤링해 서버별로 지정된 채널로 보냅니다.

전송 채널은 `/식단채널설정` 명령어로 디스코드에서 바로 바꿀 수 있고, 설정은
데이터베이스에 저장되어 재시작 후에도 유지됩니다.
"""
import logging
from datetime import time

import discord
from discord import app_commands
from discord.ext import commands, tasks

import config
import db
import menu_source
from menu_source import KST

log = logging.getLogger(__name__)


@app_commands.guild_only()
class Menu(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        if config.ENABLE_MENU_TASK:
            self.daily_menu.change_interval(
                time=time(hour=config.MENU_HOUR_KST, tzinfo=KST)
            )
            self.daily_menu.start()
        else:
            log.info("식단 자동 전송이 꺼져 있습니다. (ENABLE_MENU_TASK=0)")

    async def cog_unload(self):
        self.daily_menu.cancel()

    # ── 전송 대상 ─────────────────────────────────────

    def resolve_channel(self, guild: discord.Guild) -> discord.abc.Messageable | None:
        """해당 서버에서 식단을 보낼 채널을 찾습니다.

        명령어로 지정한 값이 우선이고, 한 번도 설정한 적이 없는 서버에 한해
        기존 `MENU_CHANNEL_ID` 환경변수를 사용합니다.
        """
        if db.has_menu_setting(guild.id):
            channel_id = db.get_menu_channel(guild.id)
        elif config.MENU_CHANNEL_ID:
            channel_id = config.MENU_CHANNEL_ID
        else:
            return None

        if channel_id is None:
            return None  # 명시적으로 해제한 서버
        channel = guild.get_channel(channel_id)
        return channel

    def targets(self) -> list[discord.abc.Messageable]:
        return [
            channel
            for guild in self.bot.guilds
            if (channel := self.resolve_channel(guild)) is not None
        ]

    # ── 매일 자동 전송 ────────────────────────────────

    @tasks.loop(time=time(hour=6, tzinfo=KST))
    async def daily_menu(self):
        channels = self.targets()
        if not channels:
            log.info("식단을 보낼 채널이 지정되지 않았습니다. (/식단채널설정)")
            return

        try:
            # 서버가 여러 곳이어도 크롤링은 한 번만 합니다.
            embed = await menu_source.build_embed()
        except Exception:
            log.exception("식단 크롤링 실패 — 오늘 전송을 건너뜁니다.")
            return

        for channel in channels:
            try:
                await channel.send(embed=embed)
            except discord.Forbidden:
                log.warning(
                    "%s 채널에 메시지를 보낼 권한이 없습니다.", channel.id
                )
            except discord.HTTPException:
                log.exception("식단 전송 실패 (채널: %s)", channel.id)

    @daily_menu.before_loop
    async def before_daily_menu(self):
        await self.bot.wait_until_ready()

    @daily_menu.error
    async def daily_menu_error(self, exc: BaseException):
        log.exception("식단 자동 전송 루프 오류", exc_info=exc)

    # ── 명령어 ────────────────────────────────────────

    @app_commands.command(name="식단", description="오늘의 식단표를 지금 불러옵니다.")
    async def menu_now(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            await interaction.followup.send(embed=await menu_source.build_embed())
        except Exception as exc:
            log.exception("식단 조회 실패")
            await interaction.followup.send(f"❌ 식단을 불러오지 못했습니다: {exc}")

    @app_commands.command(
        name="식단채널설정", description="식단을 매일 자동으로 올릴 채널을 지정합니다."
    )
    @app_commands.describe(채널="식단을 올릴 채널 (생략하면 이 명령어를 쓴 채널)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_channel(
        self,
        interaction: discord.Interaction,
        채널: discord.TextChannel | None = None,
    ):
        channel = 채널 or interaction.channel
        perms = channel.permissions_for(interaction.guild.me)
        if not (perms.send_messages and perms.embed_links):
            await interaction.response.send_message(
                f"{channel.mention} 에 메시지를 보낼 권한이 없습니다. "
                "봇에게 `메시지 보내기`와 `링크 첨부` 권한을 주세요.",
                ephemeral=True,
            )
            return

        db.set_menu_channel(interaction.guild.id, channel.id)

        embed = discord.Embed(
            title="✅ 식단 채널이 설정되었습니다",
            description=(
                f"이제 매일 **{config.MENU_HOUR_KST}시(KST)** 에 "
                f"{channel.mention} 로 식단표를 보냅니다."
            ),
            colour=discord.Colour.green(),
        )
        embed.set_footer(text="지금 바로 확인하려면 /식단 을 사용하세요.")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="식단채널해제", description="식단 자동 전송을 끕니다."
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def unset_channel(self, interaction: discord.Interaction):
        db.set_menu_channel(interaction.guild.id, None)
        await interaction.response.send_message(
            "🔕 식단 자동 전송을 껐습니다. `/식단채널설정` 으로 다시 켤 수 있습니다."
        )

    @app_commands.command(
        name="식단설정", description="현재 식단 자동 전송 설정을 확인합니다."
    )
    async def show_settings(self, interaction: discord.Interaction):
        guild = interaction.guild
        channel = self.resolve_channel(guild)

        if not config.ENABLE_MENU_TASK:
            status = "⛔ 꺼짐 (봇 전체 설정 `ENABLE_MENU_TASK=0`)"
        elif channel is not None:
            status = f"✅ 켜짐 — {channel.mention}"
        elif db.has_menu_setting(guild.id) and db.get_menu_channel(guild.id):
            # 채널은 지정됐는데 삭제되었거나 봇이 볼 수 없는 경우
            status = "⚠️ 지정된 채널을 찾을 수 없습니다. 다시 설정해 주세요."
        else:
            status = "🔕 꺼짐 — `/식단채널설정` 으로 켜세요."

        embed = discord.Embed(title="🍚 식단 자동 전송 설정", colour=discord.Colour.orange())
        embed.add_field(name="상태", value=status, inline=False)
        embed.add_field(name="전송 시각", value=f"매일 {config.MENU_HOUR_KST}시 (KST)")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── 오류 처리 ─────────────────────────────────────

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        from cogs.leveling import handle_command_error

        await handle_command_error(interaction, error)


async def setup(bot: commands.Bot):
    await bot.add_cog(Menu(bot))
