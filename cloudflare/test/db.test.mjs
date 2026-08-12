import assert from "node:assert/strict";
import { makeFakeD1, readAllMigrations } from "./fake-d1.mjs";
import * as db from "./.bundled-db.mjs";

const schema = readAllMigrations();
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

  assert.equal(await db.getMenuChannel(d1, GUILD), null);
  assert.deepEqual(await db.allMenuChannels(d1), []);

  await db.setMenuChannel(d1, GUILD, "777");
  assert.equal(await db.getMenuChannel(d1, GUILD), "777");
  assert.deepEqual(await db.allMenuChannels(d1), [{ guildId: GUILD, channelId: "777" }]);

  await db.setMenuChannel(d1, GUILD, "888"); // 덮어쓰기
  assert.equal(await db.getMenuChannel(d1, GUILD), "888");

  await db.setMenuChannel(d1, GUILD, null); // 명시적 해제
  assert.equal(await db.getMenuChannel(d1, GUILD), null);
  assert.deepEqual(await db.allMenuChannels(d1), []);

  console.log("  db.ts: 식단 채널 설정/덮어쓰기/해제 OK");
}

async function testTrafficSettings() {
  const d1 = makeFakeD1(schema);

  assert.equal(await db.getTrafficChannel(d1, GUILD), null);
  assert.deepEqual(await db.allTrafficChannels(d1), []);

  await db.setTrafficChannel(d1, GUILD, "777");
  assert.equal(await db.getTrafficChannel(d1, GUILD), "777");
  assert.deepEqual(await db.allTrafficChannels(d1), [{ guildId: GUILD, channelId: "777" }]);

  // 식단 채널 설정과 서로 간섭하지 않아야 함
  await db.setMenuChannel(d1, GUILD, "555");
  assert.equal(await db.getTrafficChannel(d1, GUILD), "777");
  assert.equal(await db.getMenuChannel(d1, GUILD), "555");

  await db.setTrafficChannel(d1, GUILD, null); // 명시적 해제
  assert.equal(await db.getTrafficChannel(d1, GUILD), null);
  assert.deepEqual(await db.allTrafficChannels(d1), []);
  assert.equal(await db.getMenuChannel(d1, GUILD), "555", "다른 설정까지 같이 지워지면 안 됨");

  console.log("  db.ts: 교통정보 채널 설정/덮어쓰기/해제 + 식단 설정과 독립 OK");
}

async function testSeenIncidents() {
  const d1 = makeFakeD1(schema);

  const first = await db.filterNewIncidentKeys(d1, ["a", "b"]);
  assert.deepEqual(first.sort(), ["a", "b"]);

  // 같은 key를 다시 넣으면 "새로운 것"으로 잡히면 안 됨
  const second = await db.filterNewIncidentKeys(d1, ["a", "b", "c"]);
  assert.deepEqual(second, ["c"]);

  console.log("  db.ts: 돌발상황 중복 알림 방지(filterNewIncidentKeys) OK");
}

await testCrud();
await testSettings();
await testTrafficSettings();
await testSeenIncidents();
console.log("db.ts 전부 통과 ✅");
