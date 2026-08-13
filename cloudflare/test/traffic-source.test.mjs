import assert from "node:assert/strict";
import * as traffic from "./.bundled-traffic-source.mjs";

// 실제 API 응답을 흉내낸 샘플: 같은 구간(conzoneId)에 VDS 센서가 여러 개
// 잡혀 항목이 중복으로 옵니다. grade는 실제 응답에서 전부 "3"이었습니다.
const SAMPLE_LIST = {
  list: [
    {
      routeNo: "0010",
      routeName: "경부선",
      conzoneId: "C001",
      conzoneName: "신탄진~회덕",
      updownTypeCode: "S",
      speed: "28",
      grade: "3",
    },
    {
      // 같은 구간(C001), 다른 VDS 센서 — 속도가 더 낮음(더 심함)
      routeNo: "0010",
      routeName: "경부선",
      conzoneId: "C001",
      conzoneName: "신탄진~회덕",
      updownTypeCode: "S",
      speed: "12",
      grade: "3",
    },
    {
      routeNo: "0025",
      routeName: "호남선",
      conzoneId: "C003",
      conzoneName: "정읍~장성",
      updownTypeCode: "E",
      speed: "20",
      grade: "3",
    },
  ],
};

function testParseIncidentsMergesDuplicateSensorsKeepingWorstSpeed() {
  const incidents = traffic.parseIncidents(SAMPLE_LIST);
  assert.equal(incidents.length, 2, "같은 구간(C001)의 중복 센서 값은 하나로 합쳐져야 함");

  const segmentC001 = incidents.find((i) => i.key === "0010|C001|S");
  assert.ok(segmentC001, "구간 키는 routeNo|conzoneId|updownTypeCode 조합이어야 함");
  assert.match(segmentC001.message, /경부선/);
  assert.match(segmentC001.message, /신탄진~회덕/);
  assert.match(segmentC001.message, /12km\/h/, "여러 센서 중 속도가 가장 낮은(가장 심한) 값을 남겨야 함");
  assert.ok(!segmentC001.message.includes("28km/h"));
  assert.equal(segmentC001.roadName, "경부선");
  assert.equal(segmentC001.kind, "정체");
  assert.equal(segmentC001.startName, "신탄진~회덕");
  assert.ok(!segmentC001.segmentText.includes("경부선"), "segmentText에는 도로명이 빠져 있어야 함(도로별로 묶을 때 중복 방지)");
  assert.match(segmentC001.segmentText, /신탄진~회덕/);
  assert.match(segmentC001.segmentText, /12km\/h/);

  const segmentC003 = incidents.find((i) => i.key === "0025|C003|E");
  assert.ok(segmentC003);
  assert.match(segmentC003.message, /호남선/);

  console.log("  parseIncidents: 같은 구간 중복 센서 → 가장 심한 속도로 병합 OK");
}

function testParseIncidentsHandlesUnexpectedShape() {
  assert.deepEqual(traffic.parseIncidents(null), []);
  assert.deepEqual(traffic.parseIncidents({}), []);
  assert.deepEqual(traffic.parseIncidents({ list: "이상한 형태" }), []);
  // 구간을 특정할 키가 없는 항목은 조용히 건너뜀
  assert.deepEqual(traffic.parseIncidents({ list: [{ speed: "10" }] }), []);
  console.log("  parseIncidents: 예상과 다른 응답 형태/키 없는 항목 → 죽지 않고 빈 배열 OK");
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

function testFormatIncidentLinesByRoadGroupsSameRoad() {
  const incidents = traffic.parseIncidents(SAMPLE_LIST);
  const lines = traffic.formatIncidentLinesByRoad(incidents);

  const gyeongbuHeaderIndex = lines.findIndex((l) => l.includes("경부선"));
  const honamHeaderIndex = lines.findIndex((l) => l.includes("호남선"));
  assert.ok(gyeongbuHeaderIndex >= 0 && honamHeaderIndex >= 0, "도로명이 헤더로 나와야 함");

  // 경부선 구간은 경부선 헤더 바로 다음 줄에, 도로명 반복 없이 나와야 함
  const gyeongbuSegmentLine = lines[gyeongbuHeaderIndex + 1];
  assert.match(gyeongbuSegmentLine, /신탄진~회덕/);
  assert.ok(!gyeongbuSegmentLine.includes("경부선"), "구간 줄에는 도로명이 중복되면 안 됨");

  console.log("  formatIncidentLinesByRoad: 같은 고속도로끼리 묶어서 표시 OK");
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

testParseIncidentsMergesDuplicateSensorsKeepingWorstSpeed();
testParseIncidentsHandlesUnexpectedShape();
testMakeIncidentEmbed();
testFormatIncidentLinesByRoadGroupsSameRoad();
await testFetchIncidentsSendsKeyAndType();
await testFetchIncidentsHandlesHttpError();
await testFetchIncidentsPrefersGivenFetcher();
console.log("traffic-source.ts 전부 통과 ✅");
