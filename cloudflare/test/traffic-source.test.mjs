import assert from "node:assert/strict";
import * as traffic from "./.bundled-traffic-source.mjs";

// 실제 API 응답(2026-08-19, /setup/debug-menu?target=traffic)에서 뽑은
// 샘플: 같은 구간(conzoneId)에 VDS 센서가 여러 개 잡혀 항목이 중복으로
// 옵니다. C001(금토JC-양재IC)은 성남~서초 구간으로 수도권, C002(신탄진
// IC-회덕JC)는 같은 경부선이지만 대전이라 수도권이 아닙니다 — 도로
// 이름만으로는 못 거르고 구간 이름까지 봐야 하는 실제 사례입니다.
const SAMPLE_LIST = {
  list: [
    {
      routeNo: "0010",
      routeName: "경부선",
      conzoneId: "C001",
      conzoneName: "금토JC-양재IC",
      updownTypeCode: "S",
      speed: "28",
      grade: "3",
    },
    {
      // 같은 구간(C001), 다른 VDS 센서 — 속도가 더 낮음(더 심함)
      routeNo: "0010",
      routeName: "경부선",
      conzoneId: "C001",
      conzoneName: "금토JC-양재IC",
      updownTypeCode: "S",
      speed: "12",
      grade: "3",
    },
    {
      // 같은 도로(경부선)지만 수도권 밖(대전) 구간
      routeNo: "0010",
      routeName: "경부선",
      conzoneId: "C002",
      conzoneName: "신탄진IC-회덕JC",
      updownTypeCode: "S",
      speed: "30",
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
  assert.equal(incidents.length, 3, "같은 구간(C001)의 중복 센서 값은 하나로 합쳐져야 함 (C001 병합 + C002 + C003)");

  const segmentC001 = incidents.find((i) => i.key === "0010|C001|S");
  assert.ok(segmentC001, "구간 키는 routeNo|conzoneId|updownTypeCode 조합이어야 함");
  assert.match(segmentC001.message, /경부선/);
  assert.match(segmentC001.message, /금토JC-양재IC/);
  assert.match(segmentC001.message, /12km\/h/, "여러 센서 중 속도가 가장 낮은(가장 심한) 값을 남겨야 함");
  assert.ok(!segmentC001.message.includes("28km/h"));
  assert.equal(segmentC001.roadName, "경부선");
  assert.equal(segmentC001.kind, "정체");
  assert.equal(segmentC001.startName, "금토JC-양재IC");
  assert.ok(!segmentC001.segmentText.includes("경부선"), "segmentText에는 도로명이 빠져 있어야 함(도로별로 묶을 때 중복 방지)");
  assert.match(segmentC001.segmentText, /금토JC-양재IC/);
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
  assert.match(gyeongbuSegmentLine, /금토JC-양재IC/);
  assert.ok(!gyeongbuSegmentLine.includes("경부선"), "구간 줄에는 도로명이 중복되면 안 됨");

  console.log("  formatIncidentLinesByRoad: 같은 고속도로끼리 묶어서 표시 OK");
}

function testIsCapitalRegionRoad() {
  assert.equal(traffic.isCapitalRegionRoad("경부선"), true);
  assert.equal(traffic.isCapitalRegionRoad("서해안선"), true);
  assert.equal(traffic.isCapitalRegionRoad("수도권제1순환선"), true);
  assert.equal(traffic.isCapitalRegionRoad("인천김포선"), true);
  assert.equal(traffic.isCapitalRegionRoad("봉담동탄선"), true);
  assert.equal(traffic.isCapitalRegionRoad("호남선"), false, "호남선은 수도권 도로가 아님");
  assert.equal(traffic.isCapitalRegionRoad("남해선"), false);
  assert.equal(traffic.isCapitalRegionRoad(undefined), false);
  console.log("  isCapitalRegionRoad: 수도권 도로 판별 OK");
}

function testIsCapitalRegionSegment() {
  // 실제 응답 사례: 같은 경부선이라도 구간에 따라 수도권/비수도권이 갈림
  assert.equal(traffic.isCapitalRegionSegment("경부선", "금토JC-양재IC"), true, "성남~서초는 수도권");
  assert.equal(traffic.isCapitalRegionSegment("경부선", "신탄진IC-회덕JC"), false, "대전은 수도권이 아님");
  assert.equal(traffic.isCapitalRegionSegment("영동선", "용인JC-양지IC"), true, "용인은 수도권");
  assert.equal(traffic.isCapitalRegionSegment("영동선", "새말IC-둔내IC"), false, "횡성(강원)은 수도권이 아님");
  // 도로 자체가 수도권 밖이면 구간 이름과 무관하게 제외
  assert.equal(traffic.isCapitalRegionSegment("호남선", "정읍~장성"), false);
  // 구간 이름이 없어도(undefined) 도로가 수도권이면 통과
  assert.equal(traffic.isCapitalRegionSegment("경부선", undefined), true);
  console.log("  isCapitalRegionSegment: 같은 도로 안에서도 수도권 밖 구간은 제외 OK");
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
  // SAMPLE_LIST에는 경부선 수도권 구간(C001)·경부선 대전 구간(C002)·
  // 호남선(C003)이 섞여 있어서, fetchIncidents는 C001만 남겨야 함.
  assert.equal(incidents.length, 1, "도로 이름이 같아도 수도권 밖 구간(C002)과 수도권 밖 도로(C003)는 걸러져야 함");
  assert.equal(incidents[0].roadName, "경부선");
  assert.equal(incidents[0].startName, "금토JC-양재IC");
  console.log("  fetchIncidents: key/type/User-Agent 전달 + 파싱 + 수도권 구간 필터링 OK");
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
testIsCapitalRegionRoad();
testIsCapitalRegionSegment();
await testFetchIncidentsSendsKeyAndType();
await testFetchIncidentsHandlesHttpError();
await testFetchIncidentsPrefersGivenFetcher();
console.log("traffic-source.ts 전부 통과 ✅");
