import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import * as ed from "@noble/ed25519";
import { makeFakeD1 } from "./fake-d1.mjs";
import * as db from "./.bundled-db.mjs";
import worker, { handleRequest } from "./.bundled-index.mjs";

const schema = readFileSync(new URL("../migrations/0001_init.sql", import.meta.url), "utf8");

function bytesToHex(bytes) {
  return Buffer.from(bytes).toString("hex");
}

async function makeKeypair() {
  const privateKey = ed.utils.randomPrivateKey();
  const publicKey = await ed.getPublicKeyAsync(privateKey);
  return { privateKey, publicKeyHex: bytesToHex(publicKey) };
}

async function signRequest(privateKey, timestamp, body) {
  const message = new TextEncoder().encode(timestamp + body);
  const signature = await ed.signAsync(message, privateKey);
  return bytesToHex(signature);
}

function fakeEnv(publicKeyHex) {
  return {
    DB: makeFakeD1(schema),
    DISCORD_TOKEN: "fake-token",
    DISCORD_APPLICATION_ID: "app",
    DISCORD_PUBLIC_KEY: publicKeyHex,
  };
}

function fakeCtx() {
  const tasks = [];
  return { ctx: { waitUntil: (p) => tasks.push(p) }, tasks };
}

async function signedRequest(privateKey, payload) {
  const body = JSON.stringify(payload);
  const timestamp = String(Math.floor(Date.now() / 1000));
  const signature = await signRequest(privateKey, timestamp, body);
  return new Request("https://example.com/interactions", {
    method: "POST",
    headers: { "X-Signature-Ed25519": signature, "X-Signature-Timestamp": timestamp },
    body,
  });
}

async function testRejectsNonPost() {
  const { publicKeyHex } = await makeKeypair();
  const env = fakeEnv(publicKeyHex);
  const { ctx } = fakeCtx();
  const res = await handleRequest(new Request("https://example.com/interactions"), env, ctx);
  assert.equal(res.status, 405);
  console.log("  GET 요청 → 405 OK");
}

async function testRejectsInvalidSignature() {
  const { privateKey } = await makeKeypair();
  const { publicKeyHex: wrongPublicKey } = await makeKeypair(); // 다른 키
  const env = fakeEnv(wrongPublicKey);
  const { ctx } = fakeCtx();

  const req = await signedRequest(privateKey, { type: 1 });
  const res = await handleRequest(req, env, ctx);
  assert.equal(res.status, 401);
  console.log("  서명 불일치(다른 키로 서명) → 401 OK");
}

async function testRejectsTamperedBody() {
  const { privateKey, publicKeyHex } = await makeKeypair();
  const env = fakeEnv(publicKeyHex);
  const { ctx } = fakeCtx();

  const timestamp = String(Math.floor(Date.now() / 1000));
  const originalBody = JSON.stringify({ type: 1 });
  const signature = await signRequest(privateKey, timestamp, originalBody);
  // 서명은 원본 body 기준인데, 실제 전송 body를 몰래 바꿔치기
  const tamperedBody = JSON.stringify({ type: 1, injected: true });
  const req = new Request("https://example.com/interactions", {
    method: "POST",
    headers: { "X-Signature-Ed25519": signature, "X-Signature-Timestamp": timestamp },
    body: tamperedBody,
  });

  const res = await handleRequest(req, env, ctx);
  assert.equal(res.status, 401, "body가 서명과 다르면 반드시 거부해야 합니다");
  console.log("  서명 이후 body 변조 → 401 OK (재전송/변조 공격 방어)");
}

async function testPingRespondsWithPong() {
  const { privateKey, publicKeyHex } = await makeKeypair();
  const env = fakeEnv(publicKeyHex);
  const { ctx } = fakeCtx();

  const req = await signedRequest(privateKey, { type: 1 });
  const res = await handleRequest(req, env, ctx);
  assert.equal(res.status, 200);
  assert.deepEqual(await res.json(), { type: 1 });
  console.log("  PING → PONG OK");
}

async function testUnknownCommandRepliesFriendly() {
  const { privateKey, publicKeyHex } = await makeKeypair();
  const env = fakeEnv(publicKeyHex);
  const { ctx } = fakeCtx();

  const req = await signedRequest(privateKey, {
    type: 2,
    token: "tok",
    guild_id: "1001",
    member: { user: { id: "1", username: "u" }, roles: [], permissions: "0" },
    data: { id: "c", name: "존재하지않는명령어", options: [] },
  });
  const res = await handleRequest(req, env, ctx);
  const out = await res.json();
  assert.match(out.data.content, /알 수 없는 명령어/);
  console.log("  알 수 없는 명령어 → 친절한 안내 (크래시 없음) OK");
}

async function testKnownCommandRoutesCorrectly() {
  const { privateKey, publicKeyHex } = await makeKeypair();
  const env = fakeEnv(publicKeyHex);
  const { ctx } = fakeCtx();

  const req = await signedRequest(privateKey, {
    type: 2,
    token: "tok",
    guild_id: "1001",
    member: { user: { id: "9001", username: "u", bot: false }, roles: [], permissions: "0" },
    data: { id: "c", name: "경험치", options: [] },
  });
  const res = await handleRequest(req, env, ctx);
  const out = await res.json();
  assert.equal(out.type, 4);
  assert.match(out.data.embeds[0].title, /9001/);
  console.log("  알려진 명령어(/경험치) → 올바른 핸들러로 라우팅 OK");
}

async function testMenuCommandDefersAndSchedulesBackground() {
  const { privateKey, publicKeyHex } = await makeKeypair();
  const env = fakeEnv(publicKeyHex);
  const { ctx, tasks } = fakeCtx();

  // performMenuNow가 실제로 fetch(menu url)을 시도하지 않도록,
  // 여기서는 defer 응답과 waitUntil 등록 여부만 확인합니다.
  globalThis.fetch = async (url) => {
    const u = url.toString();
    if (u.includes("buspia")) return new Response("", { status: 500 });
    if (u.includes("/webhooks/")) return new Response("{}", { status: 200 }); // 에러 편집 응답
    throw new Error("예상치 못한 요청: " + u);
  };

  const req = await signedRequest(privateKey, {
    type: 2,
    token: "tok",
    guild_id: "1001",
    member: { user: { id: "9001", username: "u", bot: false }, roles: [], permissions: "0" },
    data: { id: "c", name: "식단", options: [] },
  });
  const res = await handleRequest(req, env, ctx);
  const out = await res.json();
  assert.equal(out.type, 5, "3초 제한 때문에 즉시 defer(type 5) 응답을 줘야 합니다");
  assert.equal(tasks.length, 1, "실제 크롤링은 ctx.waitUntil로 백그라운드 처리되어야 합니다");
  await tasks[0]; // 백그라운드 작업도 에러 없이 끝나는지 확인 (500 → 에러 메시지로 편집 시도)
  console.log("  /식단 → 즉시 defer 응답 + 백그라운드에서 후속 처리 OK");
}

async function testHandlerErrorDoesNotCrash() {
  const { privateKey, publicKeyHex } = await makeKeypair();
  const env = fakeEnv(publicKeyHex);
  env.DB = { prepare() { throw new Error("DB 고장 시뮬레이션"); } }; // 강제로 핸들러 내부 예외 유발
  const { ctx } = fakeCtx();

  const req = await signedRequest(privateKey, {
    type: 2,
    token: "tok",
    guild_id: "1001",
    member: { user: { id: "9001", username: "u", bot: false }, roles: [], permissions: "0" },
    data: { id: "c", name: "경험치", options: [] },
  });
  const res = await handleRequest(req, env, ctx);
  assert.equal(res.status, 200, "핸들러가 예외를 던져도 500이 아니라 정상 응답으로 흡수해야 합니다");
  const out = await res.json();
  assert.match(out.data.content, /문제가 생겼습니다/);
  console.log("  핸들러 내부 예외 → 크래시 없이 안내 메시지 OK");
}

async function testRegisterCommandsRequiresToken() {
  const { publicKeyHex } = await makeKeypair();
  const env = fakeEnv(publicKeyHex);
  env.SETUP_TOKEN = "correct-token";
  const { ctx } = fakeCtx();

  globalThis.fetch = async () => {
    throw new Error("토큰이 틀리면 디스코드 API를 호출하면 안 됩니다");
  };

  const noToken = await handleRequest(
    new Request("https://example.com/setup/register-commands"),
    env,
    ctx,
  );
  assert.equal(noToken.status, 403);

  const wrongToken = await handleRequest(
    new Request("https://example.com/setup/register-commands?token=nope"),
    env,
    ctx,
  );
  assert.equal(wrongToken.status, 403);

  console.log("  /setup/register-commands: 토큰 없음/오답 → 403 + API 미호출 OK");
}

async function testRegisterCommandsSucceedsWithCorrectToken() {
  const { publicKeyHex } = await makeKeypair();
  const env = fakeEnv(publicKeyHex);
  env.SETUP_TOKEN = "correct-token";
  const { ctx } = fakeCtx();

  let calledPath;
  globalThis.fetch = async (url, init) => {
    calledPath = new URL(url.toString()).pathname;
    assert.equal(init.method, "PUT");
    const body = JSON.parse(init.body);
    return new Response(JSON.stringify(body.map((c) => ({ name: c.name }))), { status: 200 });
  };

  const res = await handleRequest(
    new Request("https://example.com/setup/register-commands?token=correct-token"),
    env,
    ctx,
  );
  assert.equal(res.status, 200);
  const out = await res.json();
  assert.equal(out.commands.length, 13);
  assert.ok(calledPath.endsWith("/applications/app/commands"));

  console.log("  /setup/register-commands: 정답 토큰 → 13개 명령어 등록 요청 OK");
}

await testRegisterCommandsRequiresToken();
await testRegisterCommandsSucceedsWithCorrectToken();
await testRejectsNonPost();
await testRejectsInvalidSignature();
await testRejectsTamperedBody();
await testPingRespondsWithPong();
await testUnknownCommandRepliesFriendly();
await testKnownCommandRoutesCorrectly();
await testMenuCommandDefersAndSchedulesBackground();
await testHandlerErrorDoesNotCrash();
console.log("index.ts (라우터) 전부 통과 ✅");
