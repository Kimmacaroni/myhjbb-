import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { makeFakeD1 } from "./fake-d1.mjs";
import * as db from "./.bundled-db.mjs";
import * as scheduled from "./.bundled-scheduled.mjs";

const schema = readFileSync(new URL("../migrations/0001_init.sql", import.meta.url), "utf8");
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

await testNoTargetsSkipsCrawl();
await testSendsToAllConfiguredGuilds();
await testOneChannelFailureDoesNotBlockOthers();
await testCrawlFailureAbortsWithoutSending();
console.log("scheduled.ts 전부 통과 ✅");
