import assert from "node:assert/strict";
import { makeFakeD1, readAllMigrations } from "./fake-d1.mjs";
import * as db from "./.bundled-db.mjs";
import * as levels from "./.bundled-levels.mjs";
import * as leveling from "./.bundled-leveling.mjs";

const schema = readAllMigrations();
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

function baseInteraction({ permissions = MANAGE_ROLES, options = [] } = {}) {
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
    data: { id: "cmd-1", name: "test", options },
  };
}

/**
 * discord.ts의 rest()가 쓰는 전역 fetch를 가로챕니다. 관리자 채널에서도
 * 일반 멤버를 지정할 수 있도록 "유저" 옵션을 멘션/ID 텍스트로 받기 때문에,
 * 이제 대상 멤버 정보는 (인터랙션에 자동으로 딸려오지 않고) GET
 * /guilds/{g}/members/{u} REST 호출로 직접 조회합니다 — 그 응답을 여기서
 * 흉내냅니다.
 */
function stubFetch({ members = {} } = {}) {
  const calls = [];
  globalThis.fetch = async (url, init) => {
    const u = url.toString();
    calls.push({ url: u, method: init?.method, body: init?.body ? JSON.parse(init.body) : undefined });

    const memberMatch = u.match(/\/guilds\/[^/]+\/members\/([^/]+)$/);
    if (memberMatch && (init?.method ?? "GET") === "GET") {
      const member = members[memberMatch[1]];
      if (!member) return new Response("찾을 수 없음", { status: 404 });
      return new Response(JSON.stringify(member), { status: 200 });
    }

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
  const calls = stubFetch({ members: { [TARGET]: { user: { id: TARGET, username: "target", bot: false }, roles: [] } } });

  const interaction = baseInteraction({
    options: [
      { name: "유저", type: 3, value: `<@${TARGET}>` },
      { name: "수량", type: 4, value: needed5 },
    ],
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
  // 이전 명령으로 이미 555(초보자) 역할을 갖고 있는 상태를 반영합니다.
  const calls = stubFetch({
    members: { [TARGET]: { user: { id: TARGET, username: "target", bot: false }, roles: ["555"] } },
  });

  const interaction = baseInteraction({
    options: [
      { name: "유저", type: 3, value: TARGET }, // ID를 그냥 숫자로 입력해도 되는지 확인
      { name: "수량", type: 4, value: needed10 - current },
    ],
  });

  const res = await leveling.handleGiveXp(env, interaction);
  assert.match(res.data.embeds[0].description, /레벨 \*\*5 → 10\*\*/);

  assert.equal(roleCallsFor(calls, "999").filter((c) => c.method === "PUT").length, 1, "고인물 역할 지급");
  assert.equal(roleCallsFor(calls, "555").filter((c) => c.method === "DELETE").length, 1, "초보자 역할 회수 (최고 등급만 유지)");

  console.log("  레벨 10 달성 → 칭호 교체(하위 회수 + 상위 지급) OK — KEEP_ONLY_HIGHEST_TITLE 동작 일치");
}

async function testPermissionDenied() {
  const env = fakeEnv();
  const calls = stubFetch({ members: { [TARGET]: { user: { id: TARGET, username: "target", bot: false }, roles: [] } } });
  const interaction = baseInteraction({
    permissions: NO_PERMS,
    options: [
      { name: "유저", type: 3, value: `<@${TARGET}>` },
      { name: "수량", type: 4, value: 100 },
    ],
  });

  const res = await leveling.handleGiveXp(env, interaction);
  assert.match(res.data.content, /역할 관리/);
  assert.equal((await db.getUser(env.DB, GUILD, TARGET)).xp, 0, "권한 없으면 경험치가 바뀌면 안 됩니다");
  assert.equal(calls.length, 0, "권한 없으면 디스코드 API를 호출하면 안 됩니다 (멤버 조회조차 하면 안 됨)");

  console.log("  권한 없는 사용자 → 거부 + DB/API 변경 없음 OK");
}

async function testCannotGiveXpToBot() {
  const env = fakeEnv();
  const BOT_ID = "8001";
  const calls = stubFetch({ members: { [BOT_ID]: { user: { id: BOT_ID, username: "bot", bot: true }, roles: [] } } });
  const interaction = baseInteraction({
    options: [
      { name: "유저", type: 3, value: `<@${BOT_ID}>` },
      { name: "수량", type: 4, value: 100 },
    ],
  });

  const res = await leveling.handleGiveXp(env, interaction);
  assert.match(res.data.content, /봇에게는/);
  assert.equal(calls.filter((c) => c.method === "PUT" || c.method === "DELETE").length, 0);

  console.log("  봇 대상 경험치 지급 차단 OK");
}

async function testRejectsInvalidOrUnknownUserInput() {
  const env = fakeEnv();
  stubFetch({});
  const garbage = baseInteraction({
    options: [
      { name: "유저", type: 3, value: "누구세요" },
      { name: "수량", type: 4, value: 100 },
    ],
  });
  const res1 = await leveling.handleGiveXp(env, garbage);
  assert.match(res1.data.content, /멘션.*유저 ID/);

  const unknown = baseInteraction({
    options: [
      { name: "유저", type: 3, value: "999999999999999999" }, // 서버에 없는 ID
      { name: "수량", type: 4, value: 100 },
    ],
  });
  const res2 = await leveling.handleGiveXp(env, unknown);
  assert.match(res2.data.content, /찾을 수 없습니다/);

  console.log("  유저 텍스트를 못 알아보거나 서버에 없으면 안내 메시지 OK");
}

async function testTakeAndSetXp() {
  const env = fakeEnv();
  stubFetch({ members: { [TARGET]: { user: { id: TARGET, username: "t", bot: false }, roles: [] } } });
  const give = baseInteraction({
    options: [
      { name: "유저", type: 3, value: `<@${TARGET}>` },
      { name: "수량", type: 4, value: 500 },
    ],
  });
  await leveling.handleGiveXp(env, give);

  const take = baseInteraction({
    options: [
      { name: "유저", type: 3, value: `<@!${TARGET}>` }, // 닉네임 멘션(<@!id>) 형태도 지원
      { name: "수량", type: 4, value: 200 },
    ],
  });
  await leveling.handleTakeXp(env, take);
  assert.equal((await db.getUser(env.DB, GUILD, TARGET)).xp, 300);

  const set = baseInteraction({
    options: [
      { name: "유저", type: 3, value: `<@${TARGET}>` },
      { name: "수량", type: 4, value: 42 },
    ],
  });
  await leveling.handleSetXp(env, set);
  assert.equal((await db.getUser(env.DB, GUILD, TARGET)).xp, 42);

  console.log("  /경험치차감, /경험치설정 OK");
}

async function testShowXpUsesInvokerWithoutOption() {
  const env = fakeEnv();
  await db.addXp(env.DB, GUILD, ADMIN, 150);
  stubFetch({});
  const interaction = baseInteraction({ options: [] }); // 유저 옵션 생략 → 본인
  const res = await leveling.handleShowXp(env, interaction);
  assert.match(res.data.embeds[0].title, new RegExp(`<@${ADMIN}>`));
  assert.match(res.data.embeds[0].fields[0].value, /\*\*1\*\*/); // 150xp → 레벨 1
  console.log("  /경험치 유저 옵션 생략 시 본인 조회 OK");
}

async function testShowXpResolvesOtherUserRegardlessOfChannel() {
  const env = fakeEnv();
  await db.addXp(env.DB, GUILD, TARGET, 150);
  const calls = stubFetch({
    members: { [TARGET]: { user: { id: TARGET, username: "target", bot: false, avatar: "abc123" }, roles: [] } },
  });
  const interaction = baseInteraction({ options: [{ name: "유저", type: 3, value: `<@${TARGET}>` }] });
  const res = await leveling.handleShowXp(env, interaction);
  assert.match(res.data.embeds[0].title, new RegExp(`<@${TARGET}>`));
  assert.ok(res.data.embeds[0].thumbnail?.url.includes("abc123"), "아바타도 REST로 조회해 반영되어야 함");
  assert.ok(
    calls.some((c) => c.url.includes(`/members/${TARGET}`)),
    "USER 옵션 없이 멘션 텍스트만으로도 멤버 정보를 직접 조회해야 함 (채널 가시성과 무관)",
  );
  console.log("  /경험치 유저:멘션 → 채널 가시성과 무관하게 대상 조회 OK");
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
await testRejectsInvalidOrUnknownUserInput();
await testTakeAndSetXp();
await testShowXpUsesInvokerWithoutOption();
await testShowXpResolvesOtherUserRegardlessOfChannel();
await testLeaderboardClampsAndUsesMentions();
console.log("leveling.ts 전부 통과 ✅");
