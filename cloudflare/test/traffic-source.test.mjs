import assert from "node:assert/strict";
import * as traffic from "./.bundled-traffic-source.mjs";

const SAMPLE_LIST = {
  list: [
    {
      routeNo: "0010",
      routeName: "경부선",
      conzoneId: "C001",
      conzoneName: "신탄진~회덕",
      updownTypeCode: "S",
      speed: "12",
      grade: "3", // 심한 정체 (숫자 코드 가정)
    },
    {
      routeNo: "0015",
      routeName: "서해안선",
      conzoneId: "C002",
      conzoneName: "서서울~안산",
      updownTypeCode: "E",
      speed: "95",
      grade: "1", // 원활 — 알림 대상 아님
    },
    {
      routeNo: "0025",
      routeName: "호남선",
      conzoneId: "C003",
      conzoneName: "정읍~장성",
      updownTypeCode: "S",
      speed: "20",
      grade: "정체", // 심한 정체 (텍스트 코드 가정)
    },
  ],
};

function testParseIncidentsKeepsOnlySevereCongestion() {
  const incidents = traffic.parseIncidents(SAMPLE_LIST);
  assert.equal(incidents.length, 2, "grade가 정체가 아닌 항목은 제외되어야 함");

  assert.equal(incidents[0].key, "0010|C001|S");
  assert.match(incidents[0].message, /경부선/);
  assert.match(incidents[0].message, /신탄진~회덕/);
  assert.match(incidents[0].message, /12km\/h/);
  assert.equal(incidents[0].roadName, "경부선");
  assert.equal(incidents[0].kind, "정체");
  assert.equal(incidents[0].startName, "신탄진~회덕");

  assert.equal(incidents[1].key, "0025|C003|S");
  assert.match(incidents[1].message, /호남선/);

  console.log("  parseIncidents: grade 숫자('3')/텍스트('정체') 코드 모두 심한 정체로 인식 + 나머지 제외 OK");
}

function testParseIncidentsHandlesUnexpectedShape() {
  assert.deepEqual(traffic.parseIncidents(null), []);
  assert.deepEqual(traffic.parseIncidents({}), []);
  assert.deepEqual(traffic.parseIncidents({ list: "이상한 형태" }), []);
  // grade가 없거나 원활이면 조용히 건너뜀
  assert.deepEqual(traffic.parseIncidents({ list: [{ routeNo: "1", conzoneId: "c" }] }), []);
  assert.deepEqual(traffic.parseIncidents({ list: [{ routeNo: "1", conzoneId: "c", grade: "1" }] }), []);
  console.log("  parseIncidents: 예상과 다른 응답 형태/비정체 항목 → 죽지 않고 빈 배열 OK");
}

function testMakeIncidentEmbed() {
  const embed = traffic.makeIncidentEmbed({
    key: "0010|C001|S",
    message: "경부선 신탄진~회덕 기점 방향 정체 중 (평균 속도 12km/h)",
    roadName: "경부선",
    kind: "정체",
    startName: "신탄진~회덕",
  });
  assert.match(embed.title, /경부선/);
  assert.match(embed.title, /정체/);
  assert.match(embed.description, /평균 속도 12km\/h/);
  assert.equal(embed.fields[0].value, "신탄진~회덕");
  console.log("  makeIncidentEmbed: 임베드 구조 OK");
}

async function testFetchIncidentsSendsKeyAndType() {
  globalThis.fetch = async (url, init) => {
    const u = new URL(url.toString());
    assert.equal(u.origin + u.pathname, traffic.HIGHWAY_API_URL);
    assert.equal(u.searchParams.get("key"), "test-key");
    assert.equal(u.searchParams.get("type"), "json");
    assert.equal(init.headers["User-Agent"], "Mozilla/5.0");
    return new Response(JSON.stringify(SAMPLE_LIST), { status: 200 });
  };
  const incidents = await traffic.fetchIncidents("test-key");
  assert.equal(incidents.length, 2);
  console.log("  fetchIncidents: key/type/User-Agent 전달 + 파싱 OK");
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

testParseIncidentsKeepsOnlySevereCongestion();
testParseIncidentsHandlesUnexpectedShape();
testMakeIncidentEmbed();
await testFetchIncidentsSendsKeyAndType();
await testFetchIncidentsHandlesHttpError();
await testFetchIncidentsPrefersGivenFetcher();
console.log("traffic-source.ts 전부 통과 ✅");
