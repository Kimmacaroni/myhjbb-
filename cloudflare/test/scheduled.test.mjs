import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { makeFakeD1 } from "./fake-d1.mjs";
import * as db from "./.bundled-db.mjs";
import * as scheduled from "./.bundled-scheduled.mjs";

const schema = readFileSync(new URL("../migrations/0001_init.sql", import.meta.url), "utf8");
const MENU_URL = "https://www.buspia.co.kr/m/intranet/subpage/my/foodtable.php";
const FIXTURE_HTML = '<html><body><div class="content">중식\n제육볶음</div></body></html>';

function fakeEnv() {
  return { DB: makeFakeD1(schema), DISCORD_TOKEN: "fake-token", DISCORD_APPLICATION_ID: "app", DISCORD_PUBLIC_KEY: "x" };
}

/**
 * 실제 Cloudflare Workers의 HTMLRewriter를 아주 단순하게 흉내낸 테스트 전용
 * 스텁입니다. div.content 안의 텍스트만 그대로 뽑아주는 정도라, 이 테스트는
 * "크롤링 실패/성공에 따라 scheduled.ts가 올바르게 반응하는지"만 확인하고,
 * 실제 HTML 파싱 정확성은 검증하지 않습니다 (그건 배포 후 /식단 으로 확인).
 */
function installFakeHTMLRewriter() {
  globalThis.HTMLRewriter = class {
    constructor() {
      this.handlers = [];
    }
    on(selector, handler) {
      this.handlers.push({ selector, handler });
      return this;
    }
    transform(response) {
      const handlers = this.handlers;
      return {
        async text() {
          const html = await response.text();
          for (const { selector, handler } of handlers) {
            if (selector === "div.content") {
              const m = html.match(/<div class="content">([\s\S]*?)<\/div>/);
              if (m) handler.text({ text: m[1] });
            }
          }
          return "";
        },
      };
    }
  };
}

function stubFetch({ menuHtml = FIXTURE_HTML, menuStatus = 200, failChannels = [] } = {}) {
  const calls = [];
  globalThis.fetch = async (url, init) => {
    const u = url.toString();
    if (u === MENU_URL) {
      calls.push({ kind: "menu" });
      return new Response(menuHtml, { status: menuStatus });
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
  assert.equal(calls.length, 0, "채널 설정이 없으면 크롤링조차 하면 안 됩니다");
  console.log("  설정된 채널 없음 → 크롤링 생략 OK");
}

async function testSendsToAllConfiguredGuilds() {
  const env = fakeEnv();
  await db.setMenuChannel(env.DB, "g1", "c1");
  await db.setMenuChannel(env.DB, "g2", "c2");
  installFakeHTMLRewriter();
  const calls = stubFetch();

  await scheduled.sendDailyMenu(env);

  assert.equal(calls.filter((c) => c.kind === "menu").length, 1, "크롤링은 서버 수와 무관하게 한 번만");
  assert.deepEqual(
    calls.filter((c) => c.kind === "send").map((c) => c.channelId).sort(),
    ["c1", "c2"],
  );
  console.log("  설정된 모든 서버로 전송 + 크롤링은 1회만 OK");
}

async function testOneChannelFailureDoesNotBlockOthers() {
  const env = fakeEnv();
  await db.setMenuChannel(env.DB, "g1", "c1");
  await db.setMenuChannel(env.DB, "g2", "c2");
  installFakeHTMLRewriter();
  const calls = stubFetch({ failChannels: ["c1"] });

  await assert.doesNotReject(() => scheduled.sendDailyMenu(env));

  const sent = calls.filter((c) => c.kind === "send").map((c) => c.channelId);
  assert.ok(sent.includes("c1") && sent.includes("c2"), "c1 실패해도 c2는 시도되어야 합니다");
  console.log("  한 채널 전송 실패해도 나머지 서버는 계속 전송 OK");
}

async function testCrawlFailureAbortsWithoutSending() {
  const env = fakeEnv();
  await db.setMenuChannel(env.DB, "g1", "c1");
  installFakeHTMLRewriter();
  const calls = stubFetch({ menuStatus: 500 });

  await assert.doesNotReject(() => scheduled.sendDailyMenu(env));
  assert.equal(calls.filter((c) => c.kind === "send").length, 0, "크롤링 실패하면 아무한테도 안 보내야 합니다");
  console.log("  크롤링 실패 → 전송 자체를 생략 OK");
}

await testNoTargetsSkipsCrawl();
await testSendsToAllConfiguredGuilds();
await testOneChannelFailureDoesNotBlockOthers();
await testCrawlFailureAbortsWithoutSending();
console.log("scheduled.ts 전부 통과 ✅");
