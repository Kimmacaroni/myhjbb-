"""SQLite 영구 저장소.

경험치와 칭호 정보를 파일에 저장합니다. 봇이 재시작되어도 데이터가 유지되도록
호스팅 환경에서 `config.DB_PATH` 위치가 영구 디스크인지 확인하세요.

sqlite3는 동기 API지만 이 봇의 쿼리는 전부 인덱스 기반 단건 조회/갱신이라
수 밀리초 이내에 끝납니다. 이벤트 루프를 의미 있게 막지 않으므로 별도의
비동기 드라이버 없이 락으로만 직렬화합니다.
"""
import sqlite3
import threading
from contextlib import contextmanager

import levels

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    guild_id      INTEGER NOT NULL,
    user_id       INTEGER NOT NULL,
    xp            INTEGER NOT NULL DEFAULT 0,
    level         INTEGER NOT NULL DEFAULT 0,
    voice_minutes INTEGER NOT NULL DEFAULT 0,
    messages      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_users_rank ON users (guild_id, xp DESC);

CREATE TABLE IF NOT EXISTS titles (
    guild_id INTEGER NOT NULL,
    role_id  INTEGER NOT NULL,
    name     TEXT    NOT NULL,
    level    INTEGER NOT NULL,
    PRIMARY KEY (guild_id, role_id)
);

CREATE INDEX IF NOT EXISTS idx_titles_level ON titles (guild_id, level);

CREATE TABLE IF NOT EXISTS guild_settings (
    guild_id        INTEGER NOT NULL PRIMARY KEY,
    menu_channel_id INTEGER
);
"""


def init(path: str) -> None:
    global _conn
    _conn = sqlite3.connect(path, check_same_thread=False)
    _conn.row_factory = sqlite3.Row
    with _lock:
        _conn.executescript(SCHEMA)
        _conn.commit()


def close() -> None:
    if _conn is not None:
        with _lock:
            _conn.close()


@contextmanager
def _tx():
    if _conn is None:
        raise RuntimeError("db.init()을 먼저 호출해야 합니다.")
    with _lock:
        try:
            yield _conn
            _conn.commit()
        except Exception:
            _conn.rollback()
            raise


# ── 경험치 ────────────────────────────────────────────

def get_user(guild_id: int, user_id: int) -> sqlite3.Row:
    with _tx() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (guild_id, user_id) VALUES (?, ?)",
            (guild_id, user_id),
        )
        return conn.execute(
            "SELECT * FROM users WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        ).fetchone()


def add_xp(
    guild_id: int,
    user_id: int,
    amount: int,
    *,
    voice_minutes: int = 0,
    messages: int = 0,
) -> tuple[int, int, int]:
    """경험치를 더하거나 뺍니다.

    Returns:
        (변경 전 레벨, 변경 후 레벨, 변경 후 누적 경험치)
    """
    with _tx() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (guild_id, user_id) VALUES (?, ?)",
            (guild_id, user_id),
        )
        row = conn.execute(
            "SELECT xp, level FROM users WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        ).fetchone()

        before_level = row["level"]
        new_xp = max(0, row["xp"] + amount)  # 경험치는 음수가 되지 않습니다
        after_level = levels.level_from_xp(new_xp)

        conn.execute(
            """UPDATE users
                  SET xp = ?, level = ?,
                      voice_minutes = voice_minutes + ?,
                      messages = messages + ?
                WHERE guild_id = ? AND user_id = ?""",
            (new_xp, after_level, voice_minutes, messages, guild_id, user_id),
        )

    return before_level, after_level, new_xp


def set_xp(guild_id: int, user_id: int, value: int) -> tuple[int, int, int]:
    """경험치를 특정 값으로 덮어씁니다."""
    current = get_user(guild_id, user_id)["xp"]
    return add_xp(guild_id, user_id, max(0, value) - current)


def leaderboard(guild_id: int, limit: int = 10) -> list[sqlite3.Row]:
    with _tx() as conn:
        return conn.execute(
            """SELECT user_id, xp, level FROM users
                WHERE guild_id = ? AND xp > 0
                ORDER BY xp DESC LIMIT ?""",
            (guild_id, limit),
        ).fetchall()


def rank_of(guild_id: int, user_id: int) -> int:
    """서버 내 경험치 순위(1위부터). 경험치가 없으면 0을 반환합니다."""
    with _tx() as conn:
        row = conn.execute(
            "SELECT xp FROM users WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        ).fetchone()
        if row is None or row["xp"] <= 0:
            return 0
        higher = conn.execute(
            "SELECT COUNT(*) AS c FROM users WHERE guild_id = ? AND xp > ?",
            (guild_id, row["xp"]),
        ).fetchone()["c"]
        return higher + 1


# ── 칭호 ──────────────────────────────────────────────

def add_title(guild_id: int, role_id: int, name: str, level: int) -> None:
    with _tx() as conn:
        conn.execute(
            """INSERT INTO titles (guild_id, role_id, name, level) VALUES (?, ?, ?, ?)
               ON CONFLICT (guild_id, role_id) DO UPDATE SET name = ?, level = ?""",
            (guild_id, role_id, name, level, name, level),
        )


def delete_title(guild_id: int, role_id: int) -> None:
    with _tx() as conn:
        conn.execute(
            "DELETE FROM titles WHERE guild_id = ? AND role_id = ?",
            (guild_id, role_id),
        )


def get_titles(guild_id: int) -> list[sqlite3.Row]:
    """요구 레벨 오름차순으로 칭호 목록을 반환합니다."""
    with _tx() as conn:
        return conn.execute(
            "SELECT role_id, name, level FROM titles WHERE guild_id = ? ORDER BY level ASC",
            (guild_id,),
        ).fetchall()


def find_title_by_name(guild_id: int, name: str) -> sqlite3.Row | None:
    with _tx() as conn:
        return conn.execute(
            "SELECT role_id, name, level FROM titles WHERE guild_id = ? AND name = ?",
            (guild_id, name),
        ).fetchone()


# ── 서버별 설정 ───────────────────────────────────────

def set_menu_channel(guild_id: int, channel_id: int | None) -> None:
    """식단을 보낼 채널을 지정합니다. None이면 자동 전송을 끕니다."""
    with _tx() as conn:
        conn.execute(
            """INSERT INTO guild_settings (guild_id, menu_channel_id) VALUES (?, ?)
               ON CONFLICT (guild_id) DO UPDATE SET menu_channel_id = ?""",
            (guild_id, channel_id, channel_id),
        )


def get_menu_channel(guild_id: int) -> int | None:
    with _tx() as conn:
        row = conn.execute(
            "SELECT menu_channel_id FROM guild_settings WHERE guild_id = ?",
            (guild_id,),
        ).fetchone()
    return row["menu_channel_id"] if row else None


def all_menu_channels() -> dict[int, int]:
    """{서버 ID: 채널 ID} — 자동 전송이 켜져 있는 서버만."""
    with _tx() as conn:
        rows = conn.execute(
            "SELECT guild_id, menu_channel_id FROM guild_settings "
            "WHERE menu_channel_id IS NOT NULL"
        ).fetchall()
    return {row["guild_id"]: row["menu_channel_id"] for row in rows}
