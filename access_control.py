"""명예회장봇 관리 명령의 공통 접근 권한."""

from __future__ import annotations

import os

import discord
from discord import app_commands

from owner_ids import parse_owner_ids

BOT_OWNER_IDS = parse_owner_ids(os.getenv("BOT_OWNER_IDS"))
ADMIN_COMMAND_NAMES = {
    "경험치", "랭킹", "경험치지급", "경험치차감", "경험치설정",
    "칭호추가", "칭호삭제", "칭호목록", "칭호동기화",
}


def is_bot_owner(user: discord.abc.User) -> bool:
    return user.id in BOT_OWNER_IDS


async def admin_or_owner(interaction: discord.Interaction) -> bool:
    """관리자 또는 지정된 봇 소유자만 통과시킵니다."""
    if is_bot_owner(interaction.user):
        return True
    permissions = getattr(interaction.user, "guild_permissions", None)
    return bool(permissions and permissions.administrator)


def admin_only():
    """관리 명령에 사용하는 데코레이터."""
    return app_commands.check(admin_or_owner)
