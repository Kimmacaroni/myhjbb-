"""경험치·레벨·경고 데이터 저장소 (SQLite).

discord.py 이벤트 루프를 막지 않도록 모든 쿼리는 asyncio.to_thread로 스레드에
넘겨 실행합니다. 커넥션은 요청마다 새로 열고 닫습니다(WAL 모드라 동시 접근에도
파일 잠금 문제가 잘 생기지 않습니다).
"""
import asyncio
import sqlite3
import time
from contextlib import closing

import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS members (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    xp INTEGER NOT NULL DEFAULT 0,
    level INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS warnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    moderator_id INTEGER NOT NULL,
    reason TEXT NOT NULL,
    created_at REAL NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _init_sync() -> None:
    with closing(_connect()) as conn:
        conn.executescript(_SCHEMA)
        conn.commit()


async def init() -> None:
    await asyncio.to_thread(_init_sync)


def xp_for_level(level: int) -> int:
    """레벨이 오를수록 필요 경험치가 늘어나도록 삼각수 형태로 증가시킵니다."""
    return 50 * level * (level + 1)


def level_for_xp(xp: int) -> int:
    level = 0
    while xp_for_level(level + 1) <= xp:
        level += 1
    return level


def _add_xp_sync(guild_id: int, user_id: int, amount: int) -> tuple[int, int, int]:
    with closing(_connect()) as conn:
        conn.execute(
            "INSERT INTO members (guild_id, user_id, xp, level) VALUES (?, ?, 0, 0) "
            "ON CONFLICT (guild_id, user_id) DO NOTHING",
            (guild_id, user_id),
        )
        xp, level = conn.execute(
            "SELECT xp, level FROM members WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        ).fetchone()
        old_level = level
        new_xp = xp + amount
        new_level = level_for_xp(new_xp)
        conn.execute(
            "UPDATE members SET xp = ?, level = ? WHERE guild_id = ? AND user_id = ?",
            (new_xp, new_level, guild_id, user_id),
        )
        conn.commit()
        return new_xp, new_level, old_level


async def add_xp(guild_id: int, user_id: int, amount: int) -> tuple[int, int, int]:
    """경험치를 더하고 (현재 경험치, 새 레벨, 이전 레벨)을 돌려줍니다."""
    return await asyncio.to_thread(_add_xp_sync, guild_id, user_id, amount)


def _get_member_sync(guild_id: int, user_id: int) -> tuple[int, int]:
    with closing(_connect()) as conn:
        row = conn.execute(
            "SELECT xp, level FROM members WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        ).fetchone()
        return row if row else (0, 0)


async def get_member(guild_id: int, user_id: int) -> tuple[int, int]:
    return await asyncio.to_thread(_get_member_sync, guild_id, user_id)


def _get_leaderboard_sync(guild_id: int, limit: int) -> list[tuple[int, int, int]]:
    with closing(_connect()) as conn:
        return conn.execute(
            "SELECT user_id, xp, level FROM members WHERE guild_id = ? "
            "ORDER BY xp DESC LIMIT ?",
            (guild_id, limit),
        ).fetchall()


async def get_leaderboard(guild_id: int, limit: int = 10) -> list[tuple[int, int, int]]:
    return await asyncio.to_thread(_get_leaderboard_sync, guild_id, limit)


def _add_warning_sync(guild_id: int, user_id: int, moderator_id: int, reason: str) -> int:
    with closing(_connect()) as conn:
        cur = conn.execute(
            "INSERT INTO warnings (guild_id, user_id, moderator_id, reason, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (guild_id, user_id, moderator_id, reason, time.time()),
        )
        conn.commit()
        return cur.lastrowid


async def add_warning(guild_id: int, user_id: int, moderator_id: int, reason: str) -> int:
    return await asyncio.to_thread(_add_warning_sync, guild_id, user_id, moderator_id, reason)


def _get_warnings_sync(guild_id: int, user_id: int) -> list[tuple[int, str, float]]:
    with closing(_connect()) as conn:
        return conn.execute(
            "SELECT moderator_id, reason, created_at FROM warnings "
            "WHERE guild_id = ? AND user_id = ? ORDER BY created_at DESC",
            (guild_id, user_id),
        ).fetchall()


async def get_warnings(guild_id: int, user_id: int) -> list[tuple[int, str, float]]:
    return await asyncio.to_thread(_get_warnings_sync, guild_id, user_id)
