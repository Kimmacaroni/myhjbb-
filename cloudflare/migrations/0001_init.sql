-- Python 버전(db.py)의 스키마를 옮긴 것이지만, ID 컬럼 타입은 다릅니다.
--
-- 디스코드 ID(스노우플레이크)는 64비트 정수라 JS의 number(53비트까지만
-- 정확)로는 정밀도가 깨집니다. 그래서 guild_id/user_id/role_id/
-- menu_channel_id는 전부 TEXT로 저장합니다. (Python 버전은 int가
-- 임의 정밀도라 이 문제가 없었지만, JS 포트에서는 반드시 TEXT여야 합니다.)

CREATE TABLE IF NOT EXISTS users (
    guild_id TEXT    NOT NULL,
    user_id  TEXT    NOT NULL,
    xp       INTEGER NOT NULL DEFAULT 0,
    level    INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_users_rank ON users (guild_id, xp DESC);

CREATE TABLE IF NOT EXISTS titles (
    guild_id TEXT    NOT NULL,
    role_id  TEXT    NOT NULL,
    name     TEXT    NOT NULL,
    level    INTEGER NOT NULL,
    PRIMARY KEY (guild_id, role_id)
);

CREATE INDEX IF NOT EXISTS idx_titles_level ON titles (guild_id, level);

CREATE TABLE IF NOT EXISTS guild_settings (
    guild_id        TEXT NOT NULL PRIMARY KEY,
    menu_channel_id TEXT
);
