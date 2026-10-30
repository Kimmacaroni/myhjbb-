"""관리자가 제목과 본문을 따로 작성하는 공지."""

import discord
import db
from discord import app_commands
from discord.ext import commands

from access_control import admin_only, admin_or_owner


def announcement_payload(title: str, body: str, embedded: bool) -> dict:
    title = " ".join(title.split())
    body = body.strip()
    if not title or not body:
        raise ValueError("제목과 내용을 모두 입력해 주세요.")
    if len(title) > 200:
        raise ValueError("제목은 200자까지 입력할 수 있습니다.")
    payload = {"allowed_mentions": discord.AllowedMentions.none()}
    if embedded:
        if len(body) > 4000:
            raise ValueError("임베드 공지 내용은 4000자까지 입력할 수 있습니다.")
        payload["embed"] = discord.Embed(
            title=f"📢 {title}", description=body, colour=discord.Colour.blurple()
        )
    else:
        text = f"# 📢 {discord.utils.escape_markdown(title)}\n\n{body}"
        if len(text) > 2000:
            raise ValueError("제목과 내용을 합친 텍스트 공지는 2000자까지 입력할 수 있습니다.")
        payload["content"] = text
    return payload


class AnnouncementModal(discord.ui.Modal):
    async def on_error(self, interaction: discord.Interaction, error: Exception):
        text = db.report_error(error, 'announcement', interaction.guild_id)
        if interaction.response.is_done():
            await interaction.followup.send(text, ephemeral=True)
        else:
            await interaction.response.send_message(text, ephemeral=True)

    def __init__(self, channel: discord.TextChannel, embedded: bool):
        super().__init__(title="임베드 공지 작성" if embedded else "텍스트 공지 작성")
        self.channel = channel
        self.embedded = embedded
        self.heading = discord.ui.TextInput(label="제목", max_length=200,
                                           placeholder="공지 제목을 입력하세요")
        self.body = discord.ui.TextInput(label="내용", style=discord.TextStyle.paragraph,
                                        max_length=4000 if embedded else 1700,
                                        placeholder="공지 내용을 입력하세요 (줄바꿈 가능)")
        self.add_item(self.heading)
        self.add_item(self.body)

    async def on_submit(self, interaction: discord.Interaction):
        # 작성 중 권한이 변경될 수 있으므로 제출 시에도 확인한다.
        if not await admin_or_owner(interaction):
            await interaction.response.send_message("공지 작성은 관리자만 사용할 수 있습니다.",
                                                    ephemeral=True)
            return
        if interaction.guild is None or self.channel.guild.id != interaction.guild.id:
            await interaction.response.send_message("이 서버의 채널에만 공지를 보낼 수 있습니다.",
                                                    ephemeral=True)
            return
        try:
            payload = announcement_payload(self.heading.value, self.body.value, self.embedded)
        except ValueError as exc:
            await interaction.response.send_message(db.report_error(exc, 'announcement', interaction.guild.id), ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            message = await self.channel.send(**payload)
        except discord.HTTPException as exc:
            await interaction.followup.send(db.report_error(exc, 'announcement', interaction.guild.id), ephemeral=True)
        else:
            await interaction.followup.send(f"✅ 공지를 게시했습니다. {message.jump_url}",
                                            ephemeral=True)


@app_commands.guild_only()
class Announcements(commands.Cog):
    async def _open(self, interaction: discord.Interaction, channel: discord.TextChannel | None,
                    embedded: bool):
        target = channel or interaction.channel
        if not isinstance(target, discord.TextChannel):
            await interaction.response.send_message("공지를 보낼 텍스트 채널을 지정해 주세요.",
                                                    ephemeral=True)
            return
        permissions = target.permissions_for(interaction.guild.me)
        if not permissions.view_channel or not permissions.send_messages or (
            embedded and not permissions.embed_links
        ):
            await interaction.response.send_message("봇이 해당 채널에 공지를 보낼 권한이 없습니다.",
                                                    ephemeral=True)
            return
        await interaction.response.send_modal(AnnouncementModal(target, embedded))

    @app_commands.command(name="공지임베드", description="제목을 강조한 임베드 공지를 작성합니다.")
    @app_commands.guild_only()
    @app_commands.describe(채널="공지를 보낼 채널 (생략하면 현재 채널)")
    @app_commands.default_permissions(administrator=True)
    @admin_only()
    async def embed_notice(self, interaction: discord.Interaction,
                           채널: discord.TextChannel | None = None):
        await self._open(interaction, 채널, True)

    @app_commands.command(name="공지텍스트", description="큰 제목과 본문을 분리한 텍스트 공지를 작성합니다.")
    @app_commands.guild_only()
    @app_commands.describe(채널="공지를 보낼 채널 (생략하면 현재 채널)")
    @app_commands.default_permissions(administrator=True)
    @admin_only()
    async def text_notice(self, interaction: discord.Interaction,
                          채널: discord.TextChannel | None = None):
        await self._open(interaction, 채널, False)

    async def cog_app_command_error(self, interaction: discord.Interaction,
                                    error: app_commands.AppCommandError):
        text = db.report_error(error, 'announcement', interaction.guild_id)
        if interaction.response.is_done():
            await interaction.followup.send(text, ephemeral=True)
        else:
            await interaction.response.send_message(text, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Announcements())
