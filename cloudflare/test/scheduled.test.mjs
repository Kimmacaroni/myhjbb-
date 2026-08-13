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
const INCIDENT_A = { routeNo: "a", conzoneId: "a", routeName: "경부선", conzoneName: "A구간", grade: "3" };
const INCIDENT_B = { routeNo: "b", conzoneId: "b", routeName: "서해안선", conzoneName: "B구간", grade: "3" };
const INCIDENT_C = { routeNo: "c", conzoneId: "c", routeName: "경부선", conzoneName: "C구간", grade: "3" };

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
      const embeds = init?.body ? JSON.parse(init.body).embeds : [];
      calls.push({ kind: "send", channelId: m[1], embedCount: embeds.length, embeds });
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
  // 이 테스트는 sendTrafficAlerts를 연달아 여러 번 부르므로, 설정된 확인
  // 주기(기본 30분) 때문에 두 번째 호출부터 조용히 건너뛰지 않도록 0으로 둡니다.
  await db.setTrafficPollIntervalMinutes(env.DB, 0);

  const calls1 = stubTrafficFetch({ incidents: [INCIDENT_A] });
  await scheduled.sendTrafficAlerts(env);
  assert.equal(calls1.filter((c) => c.kind === "traffic").length, 1);
  assert.deepEqual(
    calls1.filter((c) => c.kind === "send").map((c) => c.channelId).sort(),
    ["c1", "c2"],
    "새 정체는 설정된 모든 서버에 알려야 함",
  );

  // 같은 상황(a)이 그대로 있는 다음 폴링 — 다시 알리면 안 됨
  const calls2 = stubTrafficFetch({ incidents: [INCIDENT_A] });
  await scheduled.sendTrafficAlerts(env);
  assert.equal(calls2.filter((c) => c.kind === "send").length, 0, "이미 알린 상황은 다시 보내면 안 됩니다");

  // 새 상황(b)이 추가되면 그것만 알려야 함
  const calls3 = stubTrafficFetch({ incidents: [INCIDENT_A, INCIDENT_B] });
  await scheduled.sendTrafficAlerts(env);
  assert.equal(calls3.filter((c) => c.kind === "send").length, 2, "새로 생긴 상황(b)만 두 서버에 알려야 함");

  // a가 정체에서 풀리면(응답에서 사라지면) 알림 없이 조용히 기록만 정리
  const calls4 = stubTrafficFetch({ incidents: [INCIDENT_B] });
  await scheduled.sendTrafficAlerts(env);
  assert.equal(calls4.filter((c) => c.kind === "send").length, 0, "정체가 풀린 것 자체는 알림 대상이 아님");

  // a가 다시 정체되면 새 알림으로 잡혀야 함 (풀렸던 기록이 지워졌으므로)
  const calls5 = stubTrafficFetch({ incidents: [INCIDENT_A, INCIDENT_B] });
  await scheduled.sendTrafficAlerts(env);
  assert.equal(calls5.filter((c) => c.kind === "send").length, 2, "재발생한 정체(a)는 다시 새 알림으로 잡혀야 함");

  console.log("  sendTrafficAlerts: 모든 서버 알림 + 정체 유지 중복 방지 + 해제/재발생 감지 OK");
}

async function testTrafficMergesSameRoadIntoOneEmbed() {
  const env = fakeEnv();
  env.HIGHWAY_API_KEY = "test-key";
  await db.setTrafficChannel(env.DB, "g1", "c1");

  // A와 C는 같은 고속도로(경부선)의 서로 다른 구간, B는 다른 고속도로.
  const calls = stubTrafficFetch({ incidents: [INCIDENT_A, INCIDENT_B, INCIDENT_C] });
  await scheduled.sendTrafficAlerts(env);

  const [sent] = calls.filter((c) => c.kind === "send");
  assert.equal(sent.embedCount, 2, "경부선 구간 2개는 임베드 하나로 합치고, 서해안선은 별도 임베드로 총 2개여야 함");

  const gyeongbuEmbed = sent.embeds.find((e) => e.title.includes("경부선"));
  assert.ok(gyeongbuEmbed, "경부선 임베드가 있어야 함");
  assert.match(gyeongbuEmbed.description, /A구간/);
  assert.match(gyeongbuEmbed.description, /C구간/);

  console.log("  sendTrafficAlerts: 같은 고속도로 구간은 임베드 하나로 합쳐서 전송 OK");
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

async function testTrafficChunksMoreThan10IntoMultipleMessages() {
  const env = fakeEnv();
  env.HIGHWAY_API_KEY = "test-key";
  await db.setTrafficChannel(env.DB, "g1", "c1");

  // 디스코드 임베드 상한(10개)을 넘는, 서로 다른 고속도로 13개가 한 번에
  // 새로 잡히는 경우 (같은 도로였다면 하나로 합쳐지므로 일부러 도로를
  // 전부 다르게 함)
  const many = Array.from({ length: 13 }, (_, i) => ({
    routeNo: `r${i}`,
    conzoneId: `c${i}`,
    routeName: `도로${i}`,
    conzoneName: `${i}구간`,
    grade: "3",
  }));
  const calls = stubTrafficFetch({ incidents: many });

  await scheduled.sendTrafficAlerts(env);

  const sends = calls.filter((c) => c.kind === "send");
  assert.equal(sends.length, 2, "13개 도로면 메시지 2개(10+3)로 나뉘어 보내져야 함");
  assert.deepEqual(sends.map((c) => c.embedCount).sort((a, b) => a - b), [3, 10], "뒤쪽 도로가 조용히 누락되면 안 됨");

  console.log("  sendTrafficAlerts: 임베드 10개 초과 시 여러 메시지로 나눠 전부 전송 OK");
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

async function testTrafficRespectsConfiguredPollInterval() {
  const env = fakeEnv();
  env.HIGHWAY_API_KEY = "test-key";
  await db.setTrafficChannel(env.DB, "g1", "c1");
  await db.setTrafficPollIntervalMinutes(env.DB, 30);

  // 방금 폴링한 것으로 기록해 두면, 바로 다시 불러도 API 조회 자체를
  // 건너뛰어야 함(설정된 30분이 아직 안 지났으므로).
  await db.recordTrafficPollRan(env.DB, new Date());
  const calls1 = stubTrafficFetch({ incidents: [INCIDENT_A] });
  await scheduled.sendTrafficAlerts(env);
  assert.equal(calls1.length, 0, "설정된 주기가 안 지났으면 API 조회 자체를 하면 안 됩니다");

  // 마지막 폴링 시각을 31분 전으로 되돌리면(주기가 지난 것처럼) 다시 조회해야 함
  await db.recordTrafficPollRan(env.DB, new Date(Date.now() - 31 * 60_000));
  const calls2 = stubTrafficFetch({ incidents: [INCIDENT_A] });
  await scheduled.sendTrafficAlerts(env);
  assert.ok(calls2.some((c) => c.kind === "traffic"), "설정된 주기가 지났으면 다시 조회해야 합니다");

  console.log("  sendTrafficAlerts: /교통정보주기설정으로 정한 주기가 지나야 실제로 조회 OK");
}

await testTrafficNoOpWithoutApiKey();
await testTrafficNoOpWithoutTargets();
await testTrafficBroadcastsToAllGuildsAndDedupes();
await testTrafficMergesSameRoadIntoOneEmbed();
await testTrafficOneChannelFailureDoesNotBlockOthers();
await testTrafficChunksMoreThan10IntoMultipleMessages();
await testTrafficApiFailureDoesNotThrow();
await testTrafficRespectsConfiguredPollInterval();
console.log("scheduled.ts (교통정보) 전부 통과 ✅");
