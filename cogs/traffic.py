"""고속도로 교통정보(심한 정체 구간) 알림.

한국도로공사 Open API를 몇 분마다 확인해서, 새로 정체가 시작된 구간만
서버별로 지정된 채널에 알립니다. 정체가 계속되는 구간을 반복해서 알리지
않도록 현재 정체 중인 구간을 데이터베이스에 기록해 둡니다.

전송 채널은 `/교통정보채널설정` 명령어로 디스코드에서 바로 바꿀 수 있고,
설정은 데이터베이스에 저장되어 재시작 후에도 유지됩니다.
"""
import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands, tasks

import config
import db
import traffic_source

log = logging.getLogger(__name__)

MAX_EMBEDS = 10  # 디스코드 메시지 하나에 넣을 수 있는 임베드 최대 개수
MAX_MESSAGE_LENGTH = 2000  # 디스코드 메시지 하나의 최대 글자 수


def _chunk(items: list, size: int) -> list[list]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _chunk_text(lines: list[str], max_length: int) -> list[str]:
    """줄 단위로 이어붙이되, max_length를 넘기지 않도록 여러 메시지로 나눕니다(줄 중간에서 자르지 않음)."""
    chunks: list[str] = []
    current = ""
    for line in lines:
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > max_length and current:
            chunks.append(current)
            current = line
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


@app_commands.guild_only()
class Traffic(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        if not config.ENABLE_TRAFFIC_TASK:
            log.info("교통정보 자동 알림이 꺼져 있습니다. (ENABLE_TRAFFIC_TASK=0)")
            return
        if not config.HIGHWAY_API_KEY:
            log.info("HIGHWAY_API_KEY가 설정되지 않아 교통정보 자동 알림을 시작하지 않습니다.")
            return
        self.poll_traffic.change_interval(minutes=config.TRAFFIC_POLL_MINUTES)
        self.poll_traffic.start()

    async def cog_unload(self):
        self.poll_traffic.cancel()

    # ── 전송 대상 ─────────────────────────────────────

    def resolve_channel(self, guild: discord.Guild) -> discord.abc.Messageable | None:
        channel_id = db.get_traffic_channel(guild.id)
        if channel_id is None:
            return None
        return guild.get_channel(channel_id)

    def targets(self) -> list[discord.abc.Messageable]:
        return [
            channel
            for guild in self.bot.guilds
            if (channel := self.resolve_channel(guild)) is not None
        ]

    # ── 자동 알림 ─────────────────────────────────────

    @tasks.loop(minutes=5)
    async def poll_traffic(self):
        channels = self.targets()
        if not channels:
            return

        try:
            incidents = await asyncio.to_thread(
                traffic_source.fetch_incidents, config.HIGHWAY_API_KEY
            )
        except Exception:
            log.exception("교통정보 조회 실패")
            return

        # 정체가 하나도 없어도(빈 목록) 반드시 호출해야 합니다 — 그래야 이전에
        # 정체였다가 지금은 풀린 구간이 기록에서 지워지고, 나중에 다시
        # 정체되면 새 알림으로 잡힙니다.
        new_keys = set(db.sync_active_incidents([i["key"] for i in incidents]))
        if not new_keys:
            return

        fresh = [i for i in incidents if i["key"] in new_keys]
        # 도로마다 임베드를 따로 보내지 않고, 같은 고속도로의 구간은
        # 임베드 하나로 묶습니다.
        embed_groups = _chunk(traffic_source.make_road_embeds(fresh), MAX_EMBEDS)

        # 디스코드는 메시지 하나에 임베드 10개까지만 허용하므로, 묶고도
        # 도로 수가 많으면 여러 메시지로 나눠서 전부 보냅니다 — 뒤쪽
        # 도로가 조용히 누락되면 안 됩니다.
        for channel in channels:
            for embeds in embed_groups:
                try:
                    await channel.send(embeds=embeds)
                except discord.Forbidden:
                    log.warning("%s 채널에 메시지를 보낼 권한이 없습니다.", channel.id)
                    break
                except discord.HTTPException:
                    log.exception("교통정보 알림 실패 (채널: %s)", channel.id)
                    break

    @poll_traffic.before_loop
    async def before_poll_traffic(self):
        await self.bot.wait_until_ready()

    @poll_traffic.error
    async def poll_traffic_error(self, exc: BaseException):
        log.exception("교통정보 자동 알림 루프 오류", exc_info=exc)

    # ── 명령어 ────────────────────────────────────────

    @app_commands.command(
        name="교통정보", description="현재 고속도로 심한 정체 구간을 지금 불러옵니다."
    )
    async def traffic_now(self, interaction: discord.Interaction):
        if not config.HIGHWAY_API_KEY:
            await interaction.response.send_message(
                "❌ 교통정보 API 키(HIGHWAY_API_KEY)가 아직 설정되지 않았습니다.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()
        try:
            incidents = await asyncio.to_thread(
                traffic_source.fetch_incidents, config.HIGHWAY_API_KEY
            )
        except Exception as exc:
            log.exception("교통정보 조회 실패")
            await interaction.followup.send(f"❌ 교통정보를 불러오지 못했습니다: {exc}")
            return

        if not incidents:
            await interaction.followup.send("✅ 현재 심한 정체 구간이 없습니다.")
            return

        # 도로별로 임베드를 따로 보내던 방식에서, /교통정보로 직접 조회할
        # 때는 한 메시지 안에 고속도로별로 묶어 텍스트로 모아 보여주는
        # 방식으로 바꿨습니다(5분마다 자동으로 오는 알림은 poll_traffic에서
        # 기존 임베드 방식 그대로 유지). 디스코드 메시지 글자 수 제한(2000자)을
        # 넘을 만큼 구간이 많을 때만 예외적으로 여러 메시지로 나눠 보냅니다.
        lines = [
            f"현재 심한 정체 구간 ({len(incidents)}건)",
            *traffic_source.format_incident_lines_by_road(incidents),
        ]
        for content in _chunk_text(lines, MAX_MESSAGE_LENGTH):
            await interaction.followup.send(content=content)

    @app_commands.command(
        name="교통정보채널설정", description="고속도로 정체 구간을 자동으로 알릴 채널을 지정합니다."
    )
    @app_commands.describe(채널="알림을 보낼 채널 (생략하면 이 명령어를 쓴 채널)")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.default_permissions(manage_guild=True)
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

        db.set_traffic_channel(interaction.guild.id, channel.id)

        embed = discord.Embed(
            title="✅ 교통정보 채널이 설정되었습니다",
            description=f"이제 {channel.mention} 로 새로 시작된 고속도로 정체 구간을 자동으로 알려드립니다.",
            colour=discord.Colour.green(),
        )
        embed.set_footer(text="지금 바로 확인하려면 /교통정보 를 사용하세요.")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="교통정보채널해제", description="고속도로 정체 자동 알림을 끕니다."
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.default_permissions(manage_guild=True)
    async def unset_channel(self, interaction: discord.Interaction):
        db.set_traffic_channel(interaction.guild.id, None)
        await interaction.response.send_message(
            "🔕 교통정보 자동 알림을 껐습니다. `/교통정보채널설정` 으로 다시 켤 수 있습니다."
        )

    @app_commands.command(
        name="교통정보설정", description="현재 교통정보 자동 알림 설정을 확인합니다."
    )
    async def show_settings(self, interaction: discord.Interaction):
        guild = interaction.guild
        channel = self.resolve_channel(guild)

        if not config.ENABLE_TRAFFIC_TASK:
            status = "⛔ 꺼짐 (봇 전체 설정 `ENABLE_TRAFFIC_TASK=0`)"
        elif not config.HIGHWAY_API_KEY:
            status = "⛔ 꺼짐 (HIGHWAY_API_KEY 미설정)"
        elif channel is not None:
            status = f"✅ 켜짐 — {channel.mention}"
        elif db.get_traffic_channel(guild.id):
            status = "⚠️ 지정된 채널을 찾을 수 없습니다. 다시 설정해 주세요."
        else:
            status = "🔕 꺼짐 — `/교통정보채널설정` 으로 켜세요."

        embed = discord.Embed(title="🚧 교통정보 자동 알림 설정", colour=discord.Colour.orange())
        embed.add_field(name="상태", value=status, inline=False)
        embed.add_field(name="확인 주기", value=f"{config.TRAFFIC_POLL_MINUTES}분마다")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── 오류 처리 ─────────────────────────────────────

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        from cogs.leveling import handle_command_error

        await handle_command_error(interaction, error)


async def setup(bot: commands.Bot):
    await bot.add_cog(Traffic(bot))
