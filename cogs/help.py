""" /도움말 명령어.

봇의 명령어 트리(bot.tree)를 그대로 읽어서 목록을 만들기 때문에, 다른
Cog에서 명령어를 추가/변경해도 이 파일을 따로 고칠 필요가 없습니다.
"""
import discord
from discord import app_commands
from discord.ext import commands

from access_control import ADMIN_COMMAND_NAMES
import db


def _usage(command: app_commands.Command) -> str:
    if not command.parameters:
        return ""
    parts = [f"<{p.name}>" if p.required else f"[{p.name}]" for p in command.parameters]
    return " " + " ".join(parts)


def _permission_label(perms: discord.Permissions | None) -> str | None:
    if perms is None:
        return None
    if perms.manage_roles:
        return "역할 관리"
    if perms.manage_guild:
        return "서버 관리"
    return "관리자"


def _chunks(lines: list[str], limit: int = 1024) -> list[str]:
    """디스코드 임베드 필드 글자 제한에 맞춰 줄 목록을 나눕니다."""
    chunks: list[str] = []
    current = ""
    for line in lines:
        candidate = f"{current}\n{line}" if current else line
        if current and len(candidate) > limit:
            chunks.append(current)
            current = line
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


@app_commands.guild_only()
class Help(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name='오류코드', description='오류 코드의 뜻과 해결 방법을 확인합니다.')
    @app_commands.guild_only()
    @app_commands.describe(코드='오류 종류 코드 또는 조회코드 전체 (생략하면 코드 목록)')
    async def error_help(self, interaction: discord.Interaction, 코드: str | None = None):
        if not 코드:
            text = '\n'.join(f'`{code}` — {item[0]}' for code, item in db.ERROR_CATALOG.items())
            await interaction.response.send_message(text, ephemeral=True)
            return
        reference = 코드.strip().upper()
        code = reference if reference in db.ERROR_CATALOG else reference.rsplit('-', 1)[0]
        if code not in db.ERROR_CATALOG:
            await interaction.response.send_message('알 수 없는 코드입니다. 메시지의 조회코드 전체를 복사해 주세요.', ephemeral=True)
            return
        event = None
        if reference != code:
            event = db.lookup_error(reference, interaction.guild.id)
            if event is None:
                await interaction.response.send_message('이 서버에서 발생한 조회코드를 찾지 못했습니다. 코드가 정확한지 확인해 주세요.', ephemeral=True)
                return
        title, explanation, action = db.ERROR_CATALOG[code]
        text = f'**{title} · {code}**\n{explanation}\n{action}'
        if event:
            text += f"\n발생 시각(UTC): {event['created_at']}\n조회코드: `{event['reference']}`"
        await interaction.response.send_message(text, ephemeral=True)

    @app_commands.command(name="도움말", description="사용 가능한 명령어와 설명을 보여줍니다.")
    async def show_help(self, interaction: discord.Interaction):
        everyone: list[str] = []
        admin: list[str] = []

        for command in sorted(self.bot.tree.get_commands(), key=lambda c: c.name):
            line = f"**/{command.name}{_usage(command)}** — {command.description}"
            label = (
                "관리자"
                if command.name in ADMIN_COMMAND_NAMES
                else _permission_label(command.default_permissions)
            )
            if label:
                admin.append(f"{line} *({label} 권한 필요)*")
            else:
                everyone.append(line)

        embed = discord.Embed(title="📖 명령어 도움말", colour=discord.Colour.blurple())
        for index, chunk in enumerate(_chunks(everyone)):
            name = "누구나 사용 가능" if index == 0 else "누구나 사용 가능 (계속)"
            embed.add_field(name=name, value=chunk, inline=False)
        for index, chunk in enumerate(_chunks(admin)):
            name = "관리자 전용" if index == 0 else "관리자 전용 (계속)"
            embed.add_field(name=name, value=chunk, inline=False)
        embed.set_footer(text="<필수> · [생략 가능]")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))
