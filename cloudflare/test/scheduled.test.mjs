import assert from "node:assert/strict";
import { makeFakeD1, readAllMigrations } from "./fake-d1.mjs";
import * as db from "./.bundled-db.mjs";
import * as scheduled from "./.bundled-scheduled.mjs";

const schema = readAllMigrations();
const DAEWON_API_URL = "https://daewon-dispatch.kcy990830.workers.dev";
const FIXTURE_MENU = { today: { meals: [{ type: "중식", items: ["제육볶음"], kcal: 900 }] } };

function fakeEnv() {
  return { DB: makeFakeD1(schema), DISCORD_TOKEN: "fake-token", DISCORD_APPLICATION_ID: "app", DISCORD_PUBLIC_KEY: "x" };
}

function stubFetch({ menuBody = FIXTURE_MENU, menuStatus = 200, failChannels = [] } = {}) {
  const calls = [];
  globalThis.fetch = async (url, init) => {
    const u = url.toString();
    if (u === DAEWON_API_URL) {
      calls.push({ kind: "menu" });
      return new Response(JSON.stringify(menuBody), { status: menuStatus });
    }
    const m = u.match(/\/channels\/([^/]+)\/messages$/);
    if (m) {
      calls.push({ kind: "send", channelId: m[1] });
      if (failChannels.includes(m[1])) return new Response("금지됨", { status: 403 });
      return new Response("{}", { status: 200 });
    }
    throw new Error(`예상치 못한 요청: ${u}`);
  };
  return calls;
}

async function testNoTargetsSkipsCrawl() {
  const env = fakeEnv();
  const calls = stubFetch();
  await scheduled.sendDailyMenu(env);
  assert.equal(calls.length, 0, "채널 설정이 없으면 식단 조회조차 하면 안 됩니다");
  console.log("  설정된 채널 없음 → 식단 조회 생략 OK");
}

async function testSendsToAllConfiguredGuilds() {
  const env = fakeEnv();
  await db.setMenuChannel(env.DB, "g1", "c1");
  await db.setMenuChannel(env.DB, "g2", "c2");
  const calls = stubFetch();

  await scheduled.sendDailyMenu(env);

  assert.equal(calls.filter((c) => c.kind === "menu").length, 1, "식단 조회는 서버 수와 무관하게 한 번만");
  assert.deepEqual(
    calls.filter((c) => c.kind === "send").map((c) => c.channelId).sort(),
    ["c1", "c2"],
  );
  console.log("  설정된 모든 서버로 전송 + 식단 조회는 1회만 OK");
}

async function testOneChannelFailureDoesNotBlockOthers() {
  const env = fakeEnv();
  await db.setMenuChannel(env.DB, "g1", "c1");
  await db.setMenuChannel(env.DB, "g2", "c2");
  const calls = stubFetch({ failChannels: ["c1"] });

  await assert.doesNotReject(() => scheduled.sendDailyMenu(env));

  const sent = calls.filter((c) => c.kind === "send").map((c) => c.channelId);
  assert.ok(sent.includes("c1") && sent.includes("c2"), "c1 실패해도 c2는 시도되어야 합니다");
  console.log("  한 채널 전송 실패해도 나머지 서버는 계속 전송 OK");
}

async function testCrawlFailureAbortsWithoutSending() {
  const env = fakeEnv();
  await db.setMenuChannel(env.DB, "g1", "c1");
  const calls = stubFetch({ menuStatus: 500 });

  await assert.doesNotReject(() => scheduled.sendDailyMenu(env));
  assert.equal(calls.filter((c) => c.kind === "send").length, 0, "식단 조회 실패하면 아무한테도 안 보내야 합니다");
  console.log("  식단 조회 실패 → 전송 자체를 생략 OK");
}

async function testUsesServiceBindingWhenAvailable() {
  const env = fakeEnv();
  await db.setMenuChannel(env.DB, "g1", "c1");
  globalThis.fetch = async () => {
    throw new Error("Service Binding이 있으면 전역 fetch로 식단 API를 부르면 안 됩니다");
  };
  let bindingCalled = false;
  env.DAEWON_API = {
    fetch: async () => {
      bindingCalled = true;
      return new Response(JSON.stringify(FIXTURE_MENU), { status: 200 });
    },
  };
  // /channels/.../messages 전송은 여전히 전역 fetch(디스코드 REST)를 씁니다.
  globalThis.fetch = async (url) => {
    const m = url.toString().match(/\/channels\/([^/]+)\/messages$/);
    if (m) return new Response("{}", { status: 200 });
    throw new Error(`예상치 못한 전역 fetch 요청: ${url}`);
  };

  await scheduled.sendDailyMenu(env);
  assert.ok(bindingCalled, "env.DAEWON_API의 fetch가 호출되어야 함");
  console.log("  env.DAEWON_API(Service Binding)가 있으면 식단 조회에 그걸 사용 OK");
}

await testNoTargetsSkipsCrawl();
await testSendsToAllConfiguredGuilds();
await testOneChannelFailureDoesNotBlockOthers();
await testCrawlFailureAbortsWithoutSending();
await testUsesServiceBindingWhenAvailable();
console.log("scheduled.ts (식단) 전부 통과 ✅");

// ── 교통정보(sendTrafficAlerts) ────────────────────────

const HIGHWAY_URL_PREFIX = "https://data.ex.co.kr/openapi/odtraffic/trafficAmountByCongest";
const INCIDENT_A = { key: "a", msg: "경부선 사고", roadName: "경부선" };
const INCIDENT_B = { key: "b", msg: "서해안선 공사", roadName: "서해안선" };

function stubTrafficFetch({ incidents = [INCIDENT_A], failChannels = [] } = {}) {
  const calls = [];
  globalThis.fetch = async (url, init) => {
    const u = url.toString();
    if (u.startsWith(HIGHWAY_URL_PREFIX)) {
      calls.push({ kind: "traffic" });
      return new Response(JSON.stringify({ list: incidents }), { status: 200 });
    }
    const m = u.match(/\/channels\/([^/]+)\/messages$/);
    if (m) {
      calls.push({ kind: "send", channelId: m[1] });
      if (failChannels.includes(m[1])) return new Response("금지됨", { status: 403 });
      return new Response("{}", { status: 200 });
    }
    throw new Error(`예상치 못한 요청: ${u}`);
  };
  return calls;
}

async function testTrafficNoOpWithoutApiKey() {
  const env = fakeEnv(); // HIGHWAY_API_KEY 없음
  await db.setTrafficChannel(env.DB, "g1", "c1");
  const calls = stubTrafficFetch();
  await scheduled.sendTrafficAlerts(env);
  assert.equal(calls.length, 0, "API 키 없으면 조용히 아무것도 안 해야 합니다");
  console.log("  sendTrafficAlerts: API 키 미설정 → 조용히 건너뜀 OK");
}

async function testTrafficNoOpWithoutTargets() {
  const env = fakeEnv();
  env.HIGHWAY_API_KEY = "test-key";
  const calls = stubTrafficFetch();
  await scheduled.sendTrafficAlerts(env);
  assert.equal(calls.length, 0, "채널 설정이 없으면 API 조회조차 하면 안 됩니다");
  console.log("  sendTrafficAlerts: 설정된 채널 없음 → 조회 생략 OK");
}

async function testTrafficBroadcastsToAllGuildsAndDedupes() {
  const env = fakeEnv();
  env.HIGHWAY_API_KEY = "test-key";
  await db.setTrafficChannel(env.DB, "g1", "c1");
  await db.setTrafficChannel(env.DB, "g2", "c2");

  const calls1 = stubTrafficFetch({ incidents: [INCIDENT_A] });
  await scheduled.sendTrafficAlerts(env);
  assert.equal(calls1.filter((c) => c.kind === "traffic").length, 1);
  assert.deepEqual(
    calls1.filter((c) => c.kind === "send").map((c) => c.channelId).sort(),
    ["c1", "c2"],
    "새 돌발상황은 설정된 모든 서버에 알려야 함",
  );

  // 같은 상황(a)이 그대로 있는 다음 폴링 — 다시 알리면 안 됨
  const calls2 = stubTrafficFetch({ incidents: [INCIDENT_A] });
  await scheduled.sendTrafficAlerts(env);
  assert.equal(calls2.filter((c) => c.kind === "send").length, 0, "이미 알린 상황은 다시 보내면 안 됩니다");

  // 새 상황(b)이 추가되면 그것만 알려야 함
  const calls3 = stubTrafficFetch({ incidents: [INCIDENT_A, INCIDENT_B] });
  await scheduled.sendTrafficAlerts(env);
  assert.equal(calls3.filter((c) => c.kind === "send").length, 2, "새로 생긴 상황(b)만 두 서버에 알려야 함");

  console.log("  sendTrafficAlerts: 모든 서버 알림 + 이미 알린 상황 중복 방지 OK");
}

async function testTrafficOneChannelFailureDoesNotBlockOthers() {
  const env = fakeEnv();
  env.HIGHWAY_API_KEY = "test-key";
  await db.setTrafficChannel(env.DB, "g1", "c1");
  await db.setTrafficChannel(env.DB, "g2", "c2");
  const calls = stubTrafficFetch({ incidents: [INCIDENT_A], failChannels: ["c1"] });

  await assert.doesNotReject(() => scheduled.sendTrafficAlerts(env));
  const sent = calls.filter((c) => c.kind === "send").map((c) => c.channelId);
  assert.ok(sent.includes("c1") && sent.includes("c2"), "c1 실패해도 c2는 시도되어야 합니다");
  console.log("  sendTrafficAlerts: 한 채널 실패해도 나머지는 계속 전송 OK");
}

async function testTrafficApiFailureDoesNotThrow() {
  const env = fakeEnv();
  env.HIGHWAY_API_KEY = "test-key";
  await db.setTrafficChannel(env.DB, "g1", "c1");
  globalThis.fetch = async (url) => {
    if (url.toString().startsWith(HIGHWAY_URL_PREFIX)) return new Response("", { status: 500 });
    throw new Error("API 실패 시 채널로 전송을 시도하면 안 됩니다");
  };
  await assert.doesNotReject(() => scheduled.sendTrafficAlerts(env));
  console.log("  sendTrafficAlerts: API 조회 실패해도 죽지 않고 조용히 건너뜀 OK");
}

await testTrafficNoOpWithoutApiKey();
await testTrafficNoOpWithoutTargets();
await testTrafficBroadcastsToAllGuildsAndDedupes();
await testTrafficOneChannelFailureDoesNotBlockOthers();
await testTrafficApiFailureDoesNotThrow();
console.log("scheduled.ts (교통정보) 전부 통과 ✅");
