import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { makeFakeD1 } from "./fake-d1.mjs";
import * as db from "./.bundled-db.mjs";
import * as levels from "./.bundled-levels.mjs";
import * as leveling from "./.bundled-leveling.mjs";

const schema = readFileSync(new URL("../migrations/0001_init.sql", import.meta.url), "utf8");
const GUILD = "1001";
const ADMIN = "9001"; // 명령어를 실행하는 관리자
const TARGET = "2001"; // 경험치를 받는 대상

const MANAGE_ROLES = (1n << 28n).toString();
const NO_PERMS = "0";

function fakeEnv() {
  return {
    DB: makeFakeD1(schema),
    DISCORD_TOKEN: "fake-token",
    DISCORD_APPLICATION_ID: "app-id",
    DISCORD_PUBLIC_KEY: "unused",
  };
}

function baseInteraction({
  permissions = MANAGE_ROLES,
  options = [],
  resolvedUsers = {},
  resolvedMembers = {},
} = {}) {
  return {
    id: "interaction-1",
    application_id: "app-id",
    type: 2,
    token: "tok",
    guild_id: GUILD,
    channel_id: "5001",
    member: {
      user: { id: ADMIN, username: "admin", bot: false },
      roles: [],
      permissions,
    },
    data: {
      id: "cmd-1",
      name: "test",
      options,
      resolved: { users: resolvedUsers, members: resolvedMembers },
    },
  };
}

/** discord.ts의 rest()가 쓰는 전역 fetch를 가로채 호출 내역만 기록합니다. */
function stubFetch() {
  const calls = [];
  globalThis.fetch = async (url, init) => {
    calls.push({ url: url.toString(), method: init?.method, body: init?.body ? JSON.parse(init.body) : undefined });
    return new Response("{}", { status: 200 });
  };
  return calls;
}

function roleCallsFor(calls, roleId) {
  return calls.filter((c) => c.url.endsWith(`/roles/${roleId}`));
}

async function testGiveXpCrossesLevelAndAssignsTitle() {
  const env = fakeEnv();
  await db.addTitle(env.DB, GUILD, "555", "초보자", 5);
  await db.addTitle(env.DB, GUILD, "999", "고인물", 10);

  const needed5 = levels.totalXpForLevel(5);
  const calls = stubFetch();

  const interaction = baseInteraction({
    options: [
      { name: "유저", type: 6, value: TARGET },
      { name: "수량", type: 4, value: needed5 },
    ],
    resolvedUsers: { [TARGET]: { id: TARGET, username: "target", bot: false } },
  });

  const res = await leveling.handleGiveXp(env, interaction);
  assert.equal(res.type, 4);
  assert.match(res.data.embeds[0].description, /레벨 \*\*0 → 5\*\*/);

  const addCalls = calls.filter((c) => c.method === "PUT");
  const removeCalls = calls.filter((c) => c.method === "DELETE");
  assert.equal(addCalls.length, 1, "칭호(초보자) 역할이 딱 한 번 지급되어야 합니다");
  assert.ok(addCalls[0].url.includes(`/members/${TARGET}/roles/555`));
  assert.equal(removeCalls.length, 0, "아직 회수할 칭호가 없어야 합니다");

  console.log("  레벨 5 달성 → 칭호(초보자) 역할 자동 지급 OK");
  return env;
}

async function testLevelUpSwapsTitle(env) {
  const needed10 = levels.totalXpForLevel(10);
  const current = (await db.getUser(env.DB, GUILD, TARGET)).xp;
  const calls = stubFetch();

  const interaction = baseInteraction({
    options: [
      { name: "유저", type: 6, value: TARGET },
      { name: "수량", type: 4, value: needed10 - current },
    ],
    resolvedUsers: { [TARGET]: { id: TARGET, username: "target", bot: false } },
    // 이전 명령으로 이미 555(초보자) 역할을 갖고 있는 상태를 반영합니다.
    resolvedMembers: { [TARGET]: { roles: ["555"] } },
  });

  const res = await leveling.handleGiveXp(env, interaction);
  assert.match(res.data.embeds[0].description, /레벨 \*\*5 → 10\*\*/);

  assert.equal(roleCallsFor(calls, "999").filter((c) => c.method === "PUT").length, 1, "고인물 역할 지급");
  assert.equal(roleCallsFor(calls, "555").filter((c) => c.method === "DELETE").length, 1, "초보자 역할 회수 (최고 등급만 유지)");

  console.log("  레벨 10 달성 → 칭호 교체(하위 회수 + 상위 지급) OK — KEEP_ONLY_HIGHEST_TITLE 동작 일치");
}

async function testPermissionDenied() {
  const env = fakeEnv();
  const calls = stubFetch();
  const interaction = baseInteraction({
    permissions: NO_PERMS,
    options: [
      { name: "유저", type: 6, value: TARGET },
      { name: "수량", type: 4, value: 100 },
    ],
    resolvedUsers: { [TARGET]: { id: TARGET, username: "target", bot: false } },
  });

  const res = await leveling.handleGiveXp(env, interaction);
  assert.match(res.data.content, /역할 관리/);
  assert.equal((await db.getUser(env.DB, GUILD, TARGET)).xp, 0, "권한 없으면 경험치가 바뀌면 안 됩니다");
  assert.equal(calls.length, 0, "권한 없으면 디스코드 API를 호출하면 안 됩니다");

  console.log("  권한 없는 사용자 → 거부 + DB/API 변경 없음 OK");
}

async function testCannotGiveXpToBot() {
  const env = fakeEnv();
  const calls = stubFetch();
  const BOT_ID = "8001";
  const interaction = baseInteraction({
    options: [
      { name: "유저", type: 6, value: BOT_ID },
      { name: "수량", type: 4, value: 100 },
    ],
    resolvedUsers: { [BOT_ID]: { id: BOT_ID, username: "bot", bot: true } },
  });

  const res = await leveling.handleGiveXp(env, interaction);
  assert.match(res.data.content, /봇에게는/);
  assert.equal(calls.length, 0);

  console.log("  봇 대상 경험치 지급 차단 OK");
}

async function testTakeAndSetXp() {
  const env = fakeEnv();
  stubFetch();
  const give = baseInteraction({
    options: [
      { name: "유저", type: 6, value: TARGET },
      { name: "수량", type: 4, value: 500 },
    ],
    resolvedUsers: { [TARGET]: { id: TARGET, username: "t", bot: false } },
  });
  await leveling.handleGiveXp(env, give);

  const take = baseInteraction({
    options: [
      { name: "유저", type: 6, value: TARGET },
      { name: "수량", type: 4, value: 200 },
    ],
    resolvedUsers: { [TARGET]: { id: TARGET, username: "t", bot: false } },
  });
  await leveling.handleTakeXp(env, take);
  assert.equal((await db.getUser(env.DB, GUILD, TARGET)).xp, 300);

  const set = baseInteraction({
    options: [
      { name: "유저", type: 6, value: TARGET },
      { name: "수량", type: 4, value: 42 },
    ],
    resolvedUsers: { [TARGET]: { id: TARGET, username: "t", bot: false } },
  });
  await leveling.handleSetXp(env, set);
  assert.equal((await db.getUser(env.DB, GUILD, TARGET)).xp, 42);

  console.log("  /경험치차감, /경험치설정 OK");
}

async function testShowXpUsesInvokerWithoutOption() {
  const env = fakeEnv();
  await db.addXp(env.DB, GUILD, ADMIN, 150);
  const interaction = baseInteraction({ options: [] }); // 유저 옵션 생략 → 본인
  const res = await leveling.handleShowXp(env, interaction);
  assert.match(res.data.embeds[0].title, new RegExp(`<@${ADMIN}>`));
  assert.match(res.data.embeds[0].fields[0].value, /\*\*1\*\*/); // 150xp → 레벨 1
  console.log("  /경험치 유저 옵션 생략 시 본인 조회 OK");
}

async function testLeaderboardClampsAndUsesMentions() {
  const env = fakeEnv();
  for (let i = 0; i < 5; i++) await db.addXp(env.DB, GUILD, `${3000 + i}`, 100 * (i + 1));

  const interaction = baseInteraction({ options: [{ name: "인원", type: 4, value: 999 }] });
  const res = await leveling.handleLeaderboard(env, interaction);
  const lines = res.data.embeds[0].description.split("\n");
  assert.equal(lines.length, 5);
  assert.ok(lines[0].includes("🥇") && lines[0].includes(`<@${3004}>`), lines[0]);
  console.log("  /랭킹 인원 상한 클램프 + 멘션 표기 OK");
}

await testLevelUpSwapsTitle(await testGiveXpCrossesLevelAndAssignsTitle());
await testPermissionDenied();
await testCannotGiveXpToBot();
await testTakeAndSetXp();
await testShowXpUsesInvokerWithoutOption();
await testLeaderboardClampsAndUsesMentions();
console.log("leveling.ts 전부 통과 ✅");
