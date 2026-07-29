import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { makeFakeD1 } from "./fake-d1.mjs";
import * as db from "./.bundled-db.mjs";

const schema = readFileSync(new URL("../migrations/0001_init.sql", import.meta.url), "utf8");
const GUILD = "1001";
const USER = "2001";

async function testCrud() {
  const d1 = makeFakeD1(schema);

  const row = await db.getUser(d1, GUILD, USER);
  assert.equal(row.xp, 0);
  assert.equal(row.level, 0);

  let r = await db.addXp(d1, GUILD, USER, 100);
  assert.deepEqual([r.before, r.after, r.xp], [0, 1, 100]);

  // 차감이 음수로 내려가지 않아야 함
  r = await db.addXp(d1, GUILD, USER, -500);
  assert.deepEqual([r.before, r.after, r.xp], [1, 0, 0]);

  await db.setXp(d1, GUILD, USER, 1000);
  assert.equal((await db.getUser(d1, GUILD, USER)).xp, 1000);

  await db.addXp(d1, GUILD, "3001", 500);
  const board = await db.leaderboard(d1, GUILD, 10);
  assert.deepEqual(board.map((b) => b.user_id), [USER, "3001"]);
  assert.equal(await db.rankOf(d1, GUILD, USER), 1);
  assert.equal(await db.rankOf(d1, GUILD, "3001"), 2);
  assert.equal(await db.rankOf(d1, GUILD, "9999"), 0);

  // 길드 격리
  assert.equal((await db.getUser(d1, "9999", USER)).xp, 0);

  await db.addTitle(d1, GUILD, "10", "새싹", 5);
  await db.addTitle(d1, GUILD, "11", "고인물", 1);
  let titles = await db.getTitles(d1, GUILD);
  assert.deepEqual(titles.map((t) => t.level), [1, 5]); // 레벨 오름차순

  await db.addTitle(d1, GUILD, "10", "새싹", 7); // upsert
  assert.equal((await db.findTitleByName(d1, GUILD, "새싹")).level, 7);

  await db.deleteTitle(d1, GUILD, "10");
  assert.equal(await db.findTitleByName(d1, GUILD, "새싹"), null);

  console.log("  db.ts: CRUD/랭킹/길드격리/upsert OK");
}

async function testSettings() {
  const d1 = makeFakeD1(schema);

  assert.equal(await db.hasMenuSetting(d1, GUILD), false);
  assert.equal(await db.getMenuChannel(d1, GUILD), null);
  assert.deepEqual(await db.allMenuChannels(d1), []);

  await db.setMenuChannel(d1, GUILD, "777");
  assert.equal(await db.hasMenuSetting(d1, GUILD), true);
  assert.equal(await db.getMenuChannel(d1, GUILD), "777");
  assert.deepEqual(await db.allMenuChannels(d1), [{ guildId: GUILD, channelId: "777" }]);

  await db.setMenuChannel(d1, GUILD, "888"); // 덮어쓰기
  assert.equal(await db.getMenuChannel(d1, GUILD), "888");

  await db.setMenuChannel(d1, GUILD, null); // 명시적 해제
  assert.equal(await db.hasMenuSetting(d1, GUILD), true);
  assert.equal(await db.getMenuChannel(d1, GUILD), null);
  assert.deepEqual(await db.allMenuChannels(d1), []);

  console.log("  db.ts: 식단 채널 설정/덮어쓰기/해제/미설정 구분 OK");
}

await testCrud();
await testSettings();
console.log("db.ts 전부 통과 ✅");
