/**
 * Cloudflare D1 저장소 접근 계층. Python 버전(db.py)과 같은 스키마를 씁니다.
 *
 * 자동 채팅/통화방 경험치 적립이 없어졌으므로 messages/voice_minutes 컬럼은
 * 두지 않았습니다 (경험치는 전부 명령어로만 지급/차감됩니다).
 */
import { levelFromXp } from "./levels";

export interface UserRow {
  guild_id: string;
  user_id: string;
  xp: number;
  level: number;
}

export interface TitleRow {
  guild_id: string;
  role_id: string;
  name: string;
  level: number;
}

export async function getUser(db: D1Database, guildId: string, userId: string): Promise<UserRow> {
  await db
    .prepare(`INSERT OR IGNORE INTO users (guild_id, user_id) VALUES (?, ?)`)
    .bind(guildId, userId)
    .run();
  const row = await db
    .prepare(`SELECT * FROM users WHERE guild_id = ? AND user_id = ?`)
    .bind(guildId, userId)
    .first<UserRow>();
  return row!;
}

/** 경험치를 더하거나(양수) 빼고(음수), 변경 전/후 레벨과 최종 경험치를 반환합니다. */
export async function addXp(
  db: D1Database,
  guildId: string,
  userId: string,
  amount: number,
): Promise<{ before: number; after: number; xp: number }> {
  const current = await getUser(db, guildId, userId);
  const before = current.level;
  const newXp = Math.max(0, current.xp + amount); // 경험치는 음수가 되지 않습니다
  const after = levelFromXp(newXp);

  await db
    .prepare(`UPDATE users SET xp = ?, level = ? WHERE guild_id = ? AND user_id = ?`)
    .bind(newXp, after, guildId, userId)
    .run();

  return { before, after, xp: newXp };
}

export async function setXp(
  db: D1Database,
  guildId: string,
  userId: string,
  value: number,
): Promise<{ before: number; after: number; xp: number }> {
  const current = await getUser(db, guildId, userId);
  return addXp(db, guildId, userId, Math.max(0, value) - current.xp);
}

export async function leaderboard(
  db: D1Database,
  guildId: string,
  limit: number,
): Promise<UserRow[]> {
  const { results } = await db
    .prepare(
      `SELECT user_id, xp, level FROM users
        WHERE guild_id = ? AND xp > 0
        ORDER BY xp DESC LIMIT ?`,
    )
    .bind(guildId, limit)
    .all<UserRow>();
  return results;
}

export async function rankOf(db: D1Database, guildId: string, userId: string): Promise<number> {
  const row = await db
    .prepare(`SELECT xp FROM users WHERE guild_id = ? AND user_id = ?`)
    .bind(guildId, userId)
    .first<{ xp: number }>();
  if (!row || row.xp <= 0) return 0;

  const higher = await db
    .prepare(`SELECT COUNT(*) AS c FROM users WHERE guild_id = ? AND xp > ?`)
    .bind(guildId, row.xp)
    .first<{ c: number }>();
  return (higher?.c ?? 0) + 1;
}

// ── 칭호 ──────────────────────────────────────────────

export async function addTitle(
  db: D1Database,
  guildId: string,
  roleId: string,
  name: string,
  level: number,
): Promise<void> {
  await db
    .prepare(
      `INSERT INTO titles (guild_id, role_id, name, level) VALUES (?, ?, ?, ?)
       ON CONFLICT (guild_id, role_id) DO UPDATE SET name = ?, level = ?`,
    )
    .bind(guildId, roleId, name, level, name, level)
    .run();
}

export async function deleteTitle(db: D1Database, guildId: string, roleId: string): Promise<void> {
  await db
    .prepare(`DELETE FROM titles WHERE guild_id = ? AND role_id = ?`)
    .bind(guildId, roleId)
    .run();
}

/** 요구 레벨 오름차순. */
export async function getTitles(db: D1Database, guildId: string): Promise<TitleRow[]> {
  const { results } = await db
    .prepare(`SELECT role_id, name, level FROM titles WHERE guild_id = ? ORDER BY level ASC`)
    .bind(guildId)
    .all<TitleRow>();
  return results;
}

export async function findTitleByName(
  db: D1Database,
  guildId: string,
  name: string,
): Promise<TitleRow | null> {
  return db
    .prepare(`SELECT role_id, name, level FROM titles WHERE guild_id = ? AND name = ?`)
    .bind(guildId, name)
    .first<TitleRow>();
}

// ── 서버별 설정 ───────────────────────────────────────

export async function setMenuChannel(
  db: D1Database,
  guildId: string,
  channelId: string | null,
): Promise<void> {
  await db
    .prepare(
      `INSERT INTO guild_settings (guild_id, menu_channel_id) VALUES (?, ?)
       ON CONFLICT (guild_id) DO UPDATE SET menu_channel_id = ?`,
    )
    .bind(guildId, channelId, channelId)
    .run();
}

export async function getMenuChannel(db: D1Database, guildId: string): Promise<string | null> {
  const row = await db
    .prepare(`SELECT menu_channel_id FROM guild_settings WHERE guild_id = ?`)
    .bind(guildId)
    .first<{ menu_channel_id: string | null }>();
  return row?.menu_channel_id ?? null;
}

export async function hasMenuSetting(db: D1Database, guildId: string): Promise<boolean> {
  const row = await db
    .prepare(`SELECT 1 FROM guild_settings WHERE guild_id = ?`)
    .bind(guildId)
    .first();
  return row !== null;
}

export async function allMenuChannels(db: D1Database): Promise<{ guildId: string; channelId: string }[]> {
  const { results } = await db
    .prepare(
      `SELECT guild_id, menu_channel_id FROM guild_settings WHERE menu_channel_id IS NOT NULL`,
    )
    .all<{ guild_id: string; menu_channel_id: string }>();
  return results.map((r) => ({ guildId: r.guild_id, channelId: r.menu_channel_id }));
}
