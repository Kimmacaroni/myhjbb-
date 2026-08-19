import assert from "node:assert/strict";
import * as relay from "./.bundled-github-relay.mjs";

const REPO_PATH = "/repos/Kimmacaroni/-/contents/cloudflare/debug/traffic.json";

function decodeBase64Utf8(b64) {
  return Buffer.from(b64, "base64").toString("utf-8");
}

async function testCreatesNewFileWhenNoneExists() {
  const calls = [];
  const fetcher = {
    fetch: async (url, init) => {
      const u = new URL(url.toString());
      calls.push({ method: init?.method ?? "GET", path: u.pathname, init });
      if ((init?.method ?? "GET") === "GET") {
        return new Response("Not Found", { status: 404 });
      }
      return new Response(JSON.stringify({ content: {} }), { status: 201 });
    },
  };

  const message = await relay.relayDebugToGithub("tok", "traffic.json", "안녕 테스트", "main", fetcher);

  const putCall = calls.find((c) => c.method === "PUT");
  assert.ok(putCall, "새 파일이 없으면 PUT으로 만들어야 함");
  assert.equal(putCall.path, REPO_PATH);
  const putBody = JSON.parse(putCall.init.body);
  assert.equal(putBody.branch, "main");
  assert.ok(!("sha" in putBody), "새 파일이면 sha를 보내면 안 됨");
  assert.equal(decodeBase64Utf8(putBody.content), "안녕 테스트", "한글이 깨지지 않고 인코딩되어야 함");
  assert.match(message, /cloudflare\/debug\/traffic\.json/);
  assert.match(message, /main/);

  console.log("  relayDebugToGithub: 파일 없으면 새로 생성(sha 없이) OK");
}

async function testUpdatesExistingFileWithSha() {
  const calls = [];
  const fetcher = {
    fetch: async (url, init) => {
      const method = init?.method ?? "GET";
      calls.push({ method, init });
      if (method === "GET") {
        return new Response(JSON.stringify({ sha: "abc123" }), { status: 200 });
      }
      return new Response(JSON.stringify({ content: {} }), { status: 200 });
    },
  };

  await relay.relayDebugToGithub("tok", "menu.json", "내용", "main", fetcher);

  const putCall = calls.find((c) => c.method === "PUT");
  const putBody = JSON.parse(putCall.init.body);
  assert.equal(putBody.sha, "abc123", "기존 파일이 있으면 그 sha를 같이 보내 덮어써야 함");

  console.log("  relayDebugToGithub: 기존 파일 있으면 sha와 함께 덮어씀 OK");
}

async function testReturnsFailureMessageOnPutError() {
  const fetcher = {
    fetch: async (url, init) => {
      if ((init?.method ?? "GET") === "GET") return new Response("", { status: 404 });
      return new Response("권한 없음", { status: 403 });
    },
  };

  const message = await relay.relayDebugToGithub("bad-tok", "traffic.json", "x", "main", fetcher);
  assert.match(message, /403/);
  console.log("  relayDebugToGithub: 기록 실패 시 이유를 담은 메시지 반환 OK");
}

async function testUsesGivenBranch() {
  const calls = [];
  const fetcher = {
    fetch: async (url, init) => {
      calls.push(url.toString());
      if ((init?.method ?? "GET") === "GET") return new Response("", { status: 404 });
      return new Response("{}", { status: 201 });
    },
  };

  await relay.relayDebugToGithub("tok", "traffic.json", "x", "claude/how-it-works-x3928d", fetcher);
  assert.ok(calls.some((u) => u.includes("ref=claude%2Fhow-it-works-x3928d") || u.includes("ref=claude/how-it-works-x3928d")));
  console.log("  relayDebugToGithub: 지정한 브랜치로 조회/기록 OK");
}

await testCreatesNewFileWhenNoneExists();
await testUpdatesExistingFileWithSha();
await testReturnsFailureMessageOnPutError();
await testUsesGivenBranch();
console.log("github-relay.ts 전부 통과 ✅");
