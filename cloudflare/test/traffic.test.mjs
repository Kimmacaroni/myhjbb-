import assert from "node:assert/strict";
import { makeFakeD1, readAllMigrations } from "./fake-d1.mjs";
import * as db from "./.bundled-db.mjs";
import * as traffic from "./.bundled-traffic.mjs";

const schema = readAllMigrations();
const GUILD = "1001";
const CHANNEL = "5001";
const MANAGE_GUILD = (1n << 5n).toString();

function fakeEnv(extra = {}) {
  return {
    DB: makeFakeD1(schema),
    DISCORD_TOKEN: "fake-token",
    DISCORD_APPLICATION_ID: "app",
    DISCORD_PUBLIC_KEY: "x",
    ...extra,
  };
}

function baseInteraction({ permissions = MANAGE_GUILD, options = [], channelId = CHANNEL } = {}) {
  return {
    id: "i1",
    application_id: "app",
    type: 2,
    token: "tok",
    guild_id: GUILD,
    channel_id: channelId,
    member: { user: { id: "9001", username: "admin", bot: false }, roles: [], permissions },
    data: { id: "c1", name: "test", options },
  };
}

function stubFetch(sendShouldFail = false) {
  const calls = [];
  globalThis.fetch = async (url, init) => {
    const u = new URL(url.toString());
    calls.push({ path: u.pathname, method: init?.method ?? "GET" });
    if (u.pathname.endsWith("/messages") && init?.method === "POST") {
      if (sendShouldFail) return new Response("권한 없음", { status: 403 });
      return new Response("{}", { status: 200 });
    }
    throw new Error(`예상치 못한 요청: ${u.pathname}`);
  };
  return calls;
}

async function testSetChannelSuccessProbesBeforeSaving() {
  const env = fakeEnv();
  const calls = stubFetch(false);

  const res = await traffic.handleSetTrafficChannel(env, baseInteraction());
  assert.match(res.data.embeds[0].description, new RegExp(`<#${CHANNEL}>`));
  assert.equal(await db.getTrafficChannel(env.DB, GUILD), CHANNEL);
  assert.ok(calls.some((c) => c.method === "POST"), "채널에 실제로 확인 메시지를 보내봐야 합니다");

  console.log("  /교통정보채널설정: 실전송 테스트 성공 → DB 저장 OK");
}

async function testSetChannelFailureDoesNotSave() {
  const env = fakeEnv();
  stubFetch(true); // 403

  const res = await traffic.handleSetTrafficChannel(env, baseInteraction());
  assert.match(res.data.content, /권한이 없습니다/);
  assert.equal(await db.getTrafficChannel(env.DB, GUILD), null, "전송 실패 시 설정을 저장하면 안 됩니다");

  console.log("  /교통정보채널설정: 권한 없어 전송 실패 → 저장 안 함 OK");
}

async function testSetChannelPermissionDenied() {
  const env = fakeEnv();
  const calls = stubFetch(false);
  const res = await traffic.handleSetTrafficChannel(env, baseInteraction({ permissions: "0" }));
  assert.match(res.data.content, /서버 관리/);
  assert.equal(calls.length, 0, "권한 없으면 전송 시도조차 하면 안 됩니다");
  console.log("  /교통정보채널설정: 명령어 권한 없음 거부 OK");
}

async function testUnsetChannel() {
  const env = fakeEnv();
  await db.setTrafficChannel(env.DB, GUILD, CHANNEL);
  const res = await traffic.handleUnsetTrafficChannel(env, baseInteraction());
  assert.match(res.data.content, /껐습니다/);
  assert.equal(await db.getTrafficChannel(env.DB, GUILD), null);
  console.log("  /교통정보채널해제 OK");
}

async function testShowSettingsReflectsState() {
  const env = fakeEnv();
  let res = await traffic.handleTrafficSettings(env, baseInteraction({ permissions: "0" })); // 조회는 권한 필요 없음
  assert.match(res.data.embeds[0].fields[0].value, /꺼짐/);

  await db.setTrafficChannel(env.DB, GUILD, CHANNEL);
  res = await traffic.handleTrafficSettings(env, baseInteraction());
  assert.match(res.data.embeds[0].fields[0].value, new RegExp(`켜짐.*<#${CHANNEL}>`));

  console.log("  /교통정보설정: 상태 반영 OK");
}

async function testPerformTrafficNowWithoutApiKey() {
  const env = fakeEnv(); // HIGHWAY_API_KEY 없음
  const interaction = { token: "tok", application_id: "app" };
  const calls = [];
  globalThis.fetch = async (url, init) => {
    calls.push(url.toString());
    return new Response("{}", { status: 200 });
  };

  await traffic.performTrafficNow(env, interaction);
  const editCall = calls.find((u) => u.includes("/webhooks/"));
  assert.ok(editCall, "결과 편집(webhook) 요청이 있어야 함");
  console.log("  /교통정보: API 키 미설정 시 안내 메시지로 편집 OK");
}

async function testPerformTrafficNowReportsNoIncidents() {
  const env = fakeEnv({ HIGHWAY_API_KEY: "test-key" });
  const interaction = { token: "tok", application_id: "app" };
  let editedBody;
  globalThis.fetch = async (url, init) => {
    const u = url.toString();
    if (u.includes("data.ex.co.kr")) return new Response(JSON.stringify({ list: [] }), { status: 200 });
    if (u.includes("/webhooks/")) {
      editedBody = JSON.parse(init.body);
      return new Response("{}", { status: 200 });
    }
    throw new Error("예상치 못한 요청: " + u);
  };

  await traffic.performTrafficNow(env, interaction);
  assert.match(editedBody.content, /없습니다/);
  console.log("  /교통정보: 심한 정체 없음 → 안내 메시지 OK");
}

await testSetChannelSuccessProbesBeforeSaving();
await testSetChannelFailureDoesNotSave();
await testSetChannelPermissionDenied();
await testUnsetChannel();
await testShowSettingsReflectsState();
await testPerformTrafficNowWithoutApiKey();
await testPerformTrafficNowReportsNoIncidents();
console.log("traffic.ts 명령어 전부 통과 ✅");
