"""관리자가 제목과 본문을 따로 작성하는 공지."""

import discord
import logging
import db
from discord import app_commands
from discord.ext import commands

from access_control import admin_only, admin_or_owner

NOTICE_PERMISSIONS = discord.Permissions(view_channel=True, send_messages=True, embed_links=True)


def invite_url(client_id: int, guild=None) -> str:
    permissions = discord.Permissions(view_channel=True, send_messages=True, embed_links=True,
                                      read_message_history=True, manage_roles=True,
                                      manage_messages=True, connect=True, speak=True)
    if guild is not None and guild.me is not None:
        permissions.value |= guild.me.guild_permissions.value
    return discord.utils.oauth_url(client_id, permissions=permissions,
                                   scopes=('bot', 'applications.commands'), guild=guild or discord.utils.MISSING)


def permission_view(client_id: int, guild=None) -> discord.ui.View:
    view = discord.ui.View()
    view.add_item(discord.ui.Button(label='봇 초대·권한 추가 승인', url=invite_url(client_id, guild)))
    return view


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
    async def request_permissions(self, guild):
        if guild.me is None:
            return
        missing = NOTICE_PERMISSIONS.value & ~guild.me.guild_permissions.value
        if not missing:
            db.mark_permission_request(guild.id, 0)
            return
        if db.permission_request_sent(guild.id, missing):
            return
        try:
            owner = guild.owner or await guild.fetch_member(guild.owner_id)
            await owner.send(
                f'**{guild.name} — 명예회장봇 공지 권한 추가 요청**\n'
                '공지 기능에 채널 보기·메시지 보내기·링크 첨부 권한이 필요합니다. '
                '아래 버튼에서 기존 서버를 선택하고 승인해 주세요. 봇을 추방할 필요는 없습니다.\n'
                '채널별로 거부한 권한은 해당 채널의 권한 설정에서도 허용해야 합니다.',
                view=permission_view(guild.me.id, guild), allowed_mentions=discord.AllowedMentions.none())
        except discord.HTTPException:
            logging.getLogger(__name__).warning('공지 권한 요청 DM 전달 실패 (서버 ID %s)', guild.id)
        else:
            db.mark_permission_request(guild.id, missing)

    @commands.Cog.listener()
    async def on_ready(self):
        if not getattr(self, '_install_permissions_configured', False):
            try:
                application = await self.bot.application_info()
                params = application.install_params
                permissions = discord.Permissions((params.permissions.value if params else 0)
                                                  | NOTICE_PERMISSIONS.value)
                scopes = list(dict.fromkeys((params.scopes if params else []) + ['bot', 'applications.commands']))
                guild_config = application.guild_integration_config
                guild_params = guild_config.oauth2_install_params if guild_config else None
                guild_permissions = discord.Permissions(
                    (guild_params.permissions.value if guild_params else 0) | permissions.value)
                guild_scopes = list(dict.fromkeys((guild_params.scopes if guild_params else []) + scopes))
                await application.edit(install_params_scopes=scopes, install_params_permissions=permissions,
                                       guild_install_scopes=guild_scopes, guild_install_permissions=guild_permissions)
            except (discord.HTTPException, AttributeError):
                logging.getLogger(__name__).warning('기본 초대 권한 갱신 실패: /봇초대 링크를 사용하세요.')
            else:
                self._install_permissions_configured = True
                logging.getLogger(__name__).info('기본 초대 공지 권한 갱신 완료')
        for guild in self.bot.guilds:
            await self.request_permissions(guild)

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        await self.request_permissions(guild)

    @app_commands.command(name='봇초대', description='공지 권한을 포함한 봇 초대 링크를 확인합니다.')
    @app_commands.guild_only()
    async def invite_command(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            '처음 초대하거나 기존 서버의 봇 권한을 추가할 때 아래 버튼을 사용하세요.',
            view=permission_view(interaction.client.user.id), ephemeral=True)

    @app_commands.command(name='공지권한', description='공지 채널 권한을 확인하고 추가 승인을 요청합니다.')
    @app_commands.default_permissions(administrator=True)
    @admin_only()
    @app_commands.guild_only()
    async def notice_permissions(self, interaction: discord.Interaction, 채널: discord.TextChannel | None = None):
        target = 채널 or interaction.channel
        permissions = target.permissions_for(interaction.guild.me)
        missing = [label for name, label in (('view_channel', '채널 보기'), ('send_messages', '메시지 보내기'),
                                             ('embed_links', '링크 첨부')) if not getattr(permissions, name)]
        await interaction.response.send_message(
            ('부족한 공지 권한: ' + ', '.join(missing) if missing else '이 채널의 공지 권한이 모두 있습니다.') +
            '\n아래 버튼에서 기존 서버를 선택해 승인하세요. 채널별 거부 설정은 채널 권한에서도 허용해야 합니다.',
            view=permission_view(interaction.client.user.id, interaction.guild), ephemeral=True)

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
            await interaction.response.send_message(
                '봇이 해당 채널에 공지를 보낼 권한이 없습니다. 아래 버튼에서 권한을 추가 승인하고, '
                '채널별 거부 설정도 확인해 주세요.',
                view=permission_view(interaction.client.user.id, interaction.guild), ephemeral=True)
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
    cog = Announcements()
    cog.bot = bot
    await bot.add_cog(cog)
