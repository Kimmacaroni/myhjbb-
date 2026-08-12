import assert from "node:assert/strict";
import * as traffic from "./.bundled-traffic-source.mjs";

const SAMPLE_LIST = {
  list: [
    {
      key: "e1",
      msg: "경부선 상행 501k+500m 부근 사고로 인한 정체",
      roadName: "경부선",
      kind: "사고",
      startName: "신탄진",
      endName: "회덕",
    },
    {
      // key가 없는 경우: roadName/지점/시각으로 대체 키를 만들어야 함
      msg: "서해안선 하행 공사중",
      roadName: "서해안선",
      kind: "공사",
      startName: "서서울",
      endName: "안산",
      startDate: "20260812",
      startTime: "090000",
    },
  ],
};

function testParseIncidents() {
  const incidents = traffic.parseIncidents(SAMPLE_LIST);
  assert.equal(incidents.length, 2);
  assert.equal(incidents[0].key, "e1");
  assert.match(incidents[0].message, /사고로 인한 정체/);
  assert.equal(incidents[0].roadName, "경부선");
  assert.equal(incidents[0].kind, "사고");

  assert.ok(incidents[1].key.includes("서해안선"), "key가 없으면 다른 필드로 대체 키를 만들어야 함");
  assert.notEqual(incidents[1].key, incidents[0].key);

  console.log("  parseIncidents: 정상 목록 파싱 + key 없을 때 대체 키 생성 OK");
}

function testParseIncidentsHandlesUnexpectedShape() {
  assert.deepEqual(traffic.parseIncidents(null), []);
  assert.deepEqual(traffic.parseIncidents({}), []);
  assert.deepEqual(traffic.parseIncidents({ list: "이상한 형태" }), []);
  // 메시지 텍스트가 없는 항목은 조용히 건너뜀
  assert.deepEqual(traffic.parseIncidents({ list: [{ roadName: "경부선" }] }), []);
  console.log("  parseIncidents: 예상과 다른 응답 형태 → 죽지 않고 빈 배열 OK");
}

function testMakeIncidentEmbed() {
  const embed = traffic.makeIncidentEmbed({
    key: "e1",
    message: "경부선 상행 사고",
    roadName: "경부선",
    kind: "사고",
    startName: "신탄진",
    endName: "회덕",
  });
  assert.match(embed.title, /경부선/);
  assert.match(embed.title, /사고/);
  assert.equal(embed.description, "경부선 상행 사고");
  assert.equal(embed.fields[0].value, "신탄진 ~ 회덕");
  console.log("  makeIncidentEmbed: 임베드 구조 OK");
}

async function testFetchIncidentsSendsKeyAndType() {
  globalThis.fetch = async (url) => {
    const u = new URL(url.toString());
    assert.equal(u.origin + u.pathname, traffic.HIGHWAY_API_URL);
    assert.equal(u.searchParams.get("key"), "test-key");
    assert.equal(u.searchParams.get("type"), "json");
    return new Response(JSON.stringify(SAMPLE_LIST), { status: 200 });
  };
  const incidents = await traffic.fetchIncidents("test-key");
  assert.equal(incidents.length, 2);
  console.log("  fetchIncidents: key/type 파라미터 전달 + 파싱 OK");
}

async function testFetchIncidentsHandlesHttpError() {
  globalThis.fetch = async () => new Response("", { status: 500 });
  await assert.rejects(() => traffic.fetchIncidents("test-key"), /HTTP 500/);
  console.log("  fetchIncidents: API HTTP 오류 OK");
}

async function testFetchIncidentsPrefersGivenFetcher() {
  globalThis.fetch = async () => {
    throw new Error("전역 fetch가 아니라 넘겨준 fetcher를 써야 합니다");
  };
  let called = false;
  const fetcher = {
    fetch: async () => {
      called = true;
      return new Response(JSON.stringify({ list: [] }), { status: 200 });
    },
  };
  await traffic.fetchIncidents("test-key", fetcher);
  assert.ok(called);
  console.log("  fetchIncidents: 넘겨준 fetcher(Service Binding 등) 사용 OK");
}

testParseIncidents();
testParseIncidentsHandlesUnexpectedShape();
testMakeIncidentEmbed();
await testFetchIncidentsSendsKeyAndType();
await testFetchIncidentsHandlesHttpError();
await testFetchIncidentsPrefersGivenFetcher();
console.log("traffic-source.ts 전부 통과 ✅");
