import assert from "node:assert/strict";
import { makeFakeD1, readAllMigrations } from "./fake-d1.mjs";
import * as db from "./.bundled-db.mjs";
import * as titles from "./.bundled-titles.mjs";

const schema = readAllMigrations();
const GUILD = "1001";
const BOT_ID = "bot-1";
const MANAGE_ROLES = (1n << 28n).toString();

function fakeEnv() {
  return { DB: makeFakeD1(schema), DISCORD_TOKEN: "fake-token", DISCORD_APPLICATION_ID: "app", DISCORD_PUBLIC_KEY: "x" };
}

function baseInteraction({ permissions = MANAGE_ROLES, options = [] } = {}) {
  return {
    id: "i1",
    application_id: "app",
    type: 2,
    token: "tok",
    guild_id: GUILD,
    member: { user: { id: "9001", username: "admin", bot: false }, roles: [], permissions },
    data: { id: "c1", name: "test", options, resolved: { users: {}, members: {} } },
  };
}

let nextRoleId = 100;

/**
 * 디스코드 REST를 흉내내는 fetch 스텁. 봇 역할 position=10(가장 위)으로
 * 고정해서, 새로 만드는 칭호 역할들이 그 아래로 정렬되는지 확인합니다.
 */
function stubFetch({ guildMembers = [] } = {}) {
  const calls = [];
  const createdRoles = new Map(); // id -> {id, name, position}
  let rolePositions = new Map(); // roleId -> position, 봇 역할은 미리 세팅

  globalThis.fetch = async (url, init) => {
    const u = new URL(url.toString());
    const method = init?.method ?? "GET";
    const body = init?.body ? JSON.parse(init.body) : undefined;
    calls.push({ path: u.pathname + u.search, method, body });

    if (u.pathname === "/api/v10/users/@me") {
      return json({ id: BOT_ID });
    }
    if (u.pathname === `/api/v10/guilds/${GUILD}/members/${BOT_ID}`) {
      return json({ roles: ["bot-role"] });
    }
    if (u.pathname === `/api/v10/guilds/${GUILD}/roles` && method === "GET") {
      const all = [{ id: "bot-role", name: "bot", position: 10 }, ...createdRoles.values()];
      return json(all);
    }
    if (u.pathname === `/api/v10/guilds/${GUILD}/roles` && method === "POST") {
      const id = `role-${nextRoleId++}`;
      const role = { id, name: body.name, position: 1 };
      createdRoles.set(id, role);
      return json(role);
    }
    if (u.pathname === `/api/v10/guilds/${GUILD}/roles` && method === "PATCH") {
      for (const p of body) {
        if (createdRoles.has(p.id)) createdRoles.get(p.id).position = p.position;
      }
      return json({});
    }
    if (method === "DELETE" && u.pathname.startsWith(`/api/v10/guilds/${GUILD}/roles/`)) {
      const id = u.pathname.split("/").pop();
      createdRoles.delete(id);
      return json({});
    }
    if (u.pathname === `/api/v10/guilds/${GUILD}/members` && method === "GET") {
      return json(guildMembers);
    }
    if (/\/members\/.+\/roles\/.+/.test(u.pathname)) {
      return json({}); // 역할 지급/회수
    }
    throw new Error(`예상치 못한 요청: ${method} ${u.pathname}`);
  };

  return { calls, createdRoles };
}

function json(body) {
  return new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } });
}

async function testParseColour() {
  assert.equal(titles.parseColour("#E74C3C"), 0xe74c3c);
  assert.equal(titles.parseColour("E74C3C"), 0xe74c3c);
  assert.equal(titles.parseColour("헛소리"), 0);
  assert.equal(titles.parseColour(undefined), 0);
  console.log("  parseColour: #포함/미포함/잘못된값/undefined OK");
}

async function testAddTitleCreatesRoleAndSyncsPosition() {
  const env = fakeEnv();
  const { calls, createdRoles } = stubFetch();

  const interaction = baseInteraction({
    options: [
      { name: "이름", type: 3, value: "초보자" },
      { name: "레벨", type: 4, value: 5 },
      { name: "색상", type: 3, value: "#00FF00" },
    ],
  });

  const res = await titles.handleAddTitle(env, interaction);
  assert.match(res.data.embeds[0].description, /필요 레벨 \*\*5\*\*/);

  const created = [...createdRoles.values()][0];
  assert.equal(created.name, "초보자");

  const stored = await db.findTitleByName(env.DB, GUILD, "초보자");
  assert.equal(stored.role_id, created.id);
  assert.equal(stored.level, 5);

  const patchCall = calls.find((c) => c.method === "PATCH");
  assert.ok(patchCall, "역할 순서 재정렬(PATCH)이 호출되어야 합니다");
  assert.equal(patchCall.body[0].position, 9, "봇 역할(10) 바로 아래에 배치되어야 합니다");

  console.log("  /칭호추가: 역할 생성 + DB 저장 + 위치 재정렬 OK");
}

async function testAddTitleRejectsDuplicateName() {
  const env = fakeEnv();
  await db.addTitle(env.DB, GUILD, "role-1", "중복이름", 3);
  const { calls } = stubFetch();

  const interaction = baseInteraction({
    options: [
      { name: "이름", type: 3, value: "중복이름" },
      { name: "레벨", type: 4, value: 1 },
    ],
  });
  const res = await titles.handleAddTitle(env, interaction);
  assert.match(res.data.content, /이미.*중복이름/);
  assert.equal(calls.length, 0, "중복이면 디스코드 API를 호출하면 안 됩니다");
  console.log("  /칭호추가: 중복 이름 거부 + API 미호출 OK");
}

async function testRemoveTitleDeletesRoleAndDbEntry() {
  const env = fakeEnv();
  const { calls } = stubFetch();

  await titles.handleAddTitle(env, baseInteraction({
    options: [
      { name: "이름", type: 3, value: "삭제될칭호" },
      { name: "레벨", type: 4, value: 2 },
    ],
  }));
  const before = await db.findTitleByName(env.DB, GUILD, "삭제될칭호");
  assert.ok(before);

  const res = await titles.handleRemoveTitle(env, baseInteraction({
    options: [{ name: "이름", type: 3, value: "삭제될칭호" }],
  }));
  assert.match(res.data.content, /삭제했습니다/);
  assert.equal(await db.findTitleByName(env.DB, GUILD, "삭제될칭호"), null);
  assert.ok(calls.some((c) => c.method === "DELETE" && c.path.includes(`/roles/${before.role_id}`)));

  console.log("  /칭호삭제: 역할 삭제 + DB 정리 OK");
}

async function testListTitlesOrderedHighestFirst() {
  const env = fakeEnv();
  await db.addTitle(env.DB, GUILD, "r1", "새싹", 1);
  await db.addTitle(env.DB, GUILD, "r2", "고인물", 10);
  await db.addTitle(env.DB, GUILD, "r3", "중간", 5);

  const res = await titles.handleListTitles(env, baseInteraction());
  const lines = res.data.embeds[0].description.split("\n");
  assert.deepEqual(lines, [
    "**Lv.10** — <@&r2>",
    "**Lv.5** — <@&r3>",
    "**Lv.1** — <@&r1>",
  ]);
  console.log("  /칭호목록: 높은 등급 우선 정렬 OK");
}

async function testResyncCapsMembersPerInvocation() {
  const env = fakeEnv();
  await db.addTitle(env.DB, GUILD, "r1", "칭호", 1);

  // 25명 멤버 중 20명만 이번 호출에서 처리되어야 합니다 (Workers 무료 요금제 한도 대응).
  const members = Array.from({ length: 25 }, (_, i) => ({
    user: { id: `member-${i}`, username: `u${i}`, bot: false },
    roles: [],
  }));
  for (const m of members) {
    await db.addXp(env.DB, GUILD, m.user.id, 200); // 레벨 1 이상 달성
  }

  const { calls } = stubFetch({ guildMembers: members });
  const res = await titles.handleResyncTitles(env, baseInteraction());

  assert.match(res.data.content, /20명 처리했고 5명이 남았습니다/);

  const roleGrantCalls = calls.filter((c) => c.method === "PUT" && c.path.includes("/roles/r1"));
  assert.equal(roleGrantCalls.length, 20, "정확히 20명에게만 역할을 지급해야 합니다");

  console.log("  /칭호동기화: 20명 상한 적용 + 남은 인원 안내 OK");
}

async function testResyncPermissionDenied() {
  const env = fakeEnv();
  const { calls } = stubFetch();
  const res = await titles.handleResyncTitles(env, baseInteraction({ permissions: "0" }));
  assert.match(res.data.content, /역할 관리/);
  assert.equal(calls.length, 0);
  console.log("  /칭호동기화: 권한 없음 거부 OK");
}

await testParseColour();
await testAddTitleCreatesRoleAndSyncsPosition();
await testAddTitleRejectsDuplicateName();
await testRemoveTitleDeletesRoleAndDbEntry();
await testListTitlesOrderedHighestFirst();
await testResyncCapsMembersPerInvocation();
await testResyncPermissionDenied();
console.log("titles.ts 전부 통과 ✅");
