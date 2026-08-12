import assert from "node:assert/strict";
import * as menu from "./.bundled-menu-source.mjs";

const DAEWON_API_URL = "https://daewon-dispatch.kcy990830.workers.dev";

function testKstDateString() {
  // UTC 2026-07-28 15:30 = KST 2026-07-29 00:30 (자정을 넘는 경계 확인)
  const d = new Date("2026-07-28T15:30:00Z");
  assert.equal(menu.kstDateString(d), "2026년 07월 29일");
  console.log("  kstDateString: UTC→KST 자정 경계 변환 + 0패딩 OK");
}

function testFormatMealsText() {
  const meals = [
    { type: "조식", items: ["쌀밥", "된장국"], kcal: 500 },
    { type: "중식", items: ["제육볶음"], kcal: 900 },
    { type: "석식", items: ["고등어구이"] },
  ];
  const text = menu.formatMealsText(meals);
  assert.equal(text.split("─".repeat(20)).length - 1, 2, "구분선이 2번(중식/석식) 들어가야 함");
  assert.ok(text.indexOf("─".repeat(20)) < text.indexOf("중식"));
  assert.match(text, /조식 \(500Kcal\)/);
  assert.ok(!text.includes("석식 (")); // kcal 없으면 괄호도 없어야 함
  assert.ok(text.includes("고등어구이"));
  console.log("  formatMealsText: 구분선 삽입 + kcal 표기 OK");

  assert.throws(() => menu.formatMealsText([]), /식단 정보가 없습니다/);
  assert.throws(() => menu.formatMealsText(undefined), /식단 정보가 없습니다/);
  console.log("  formatMealsText: 끼니 정보가 없으면 예외 OK");
}

function testFormatMealsTextKeepsOnlyFirstDay() {
  // 실제 API가 준 응답: 5일치가 조식/중식/석식 반복으로 한 배열에 이어붙어 옴.
  const meals = [
    { type: "조식", items: ["오늘아침"], kcal: 500 },
    { type: "중식", items: ["오늘점심"], kcal: 900 },
    { type: "석식", items: ["오늘저녁"], kcal: 700 },
    { type: "조식", items: ["내일아침"], kcal: 500 },
    { type: "중식", items: ["내일점심"], kcal: 900 },
    { type: "석식", items: ["내일저녁"], kcal: 700 },
    { type: "조식", items: ["모레아침"], kcal: 500 },
    { type: "중식", items: ["모레점심"], kcal: 900 },
    { type: "석식", items: ["모레저녁"], kcal: 700 },
  ];
  const text = menu.formatMealsText(meals);
  assert.ok(text.includes("오늘아침") && text.includes("오늘점심") && text.includes("오늘저녁"));
  assert.ok(!text.includes("내일아침") && !text.includes("모레아침"), "오늘 이후 날짜는 잘려야 함");
  assert.equal(text.split("─".repeat(20)).length - 1, 2, "오늘 몫만 남아 구분선도 2번이어야 함");
  console.log("  formatMealsText: 여러 날이 이어붙어 와도 맨 앞 하루(오늘)만 남기기 OK");

  // 하루치만 오는 정상 케이스는 그대로 다 남아야 함 (오탐 방지)
  const singleDay = [
    { type: "조식", items: ["아침"] },
    { type: "중식", items: ["점심"] },
  ];
  const singleDayResult = menu.formatMealsText(singleDay);
  assert.ok(singleDayResult.includes("아침") && singleDayResult.includes("점심"));
}

function testMakeMenuEmbed() {
  const embed = menu.makeMenuEmbed("중식\n제육볶음", new Date("2026-07-29T00:00:00Z"));
  assert.match(embed.title, /식단 브리핑/);
  assert.match(embed.description, /제육볶음/);
  assert.match(embed.description, /\*\*날짜: \d{4}년 \d{2}월 \d{2}일\*\*/);
  assert.equal(embed.color, 15158332);
  console.log("  makeMenuEmbed: 임베드 구조 OK");
}

async function testFetchMenuSuccess() {
  globalThis.fetch = async (url, init) => {
    assert.equal(url.toString(), DAEWON_API_URL);
    assert.equal(init.method, "POST");
    assert.deepEqual(JSON.parse(init.body), { action: "foodmenu" });
    return new Response(
      JSON.stringify({
        today: { date: "2026-07-29", meals: [{ type: "중식", items: ["제육볶음"], kcal: 900 }] },
        tomorrow: { date: "2026-07-30", meals: [{ type: "중식", items: ["돈까스"] }] },
      }),
      { status: 200 },
    );
  };
  const text = await menu.fetchMenu();
  assert.ok(text.includes("제육볶음"), "오늘 식단만 포함되어야 함");
  assert.ok(!text.includes("돈까스"), "내일 식단은 포함되면 안 됨");
  console.log("  fetchMenu: API 정상 응답 → 오늘 식단만 텍스트로 변환 OK");
}

async function testFetchMenuHandlesErrors() {
  globalThis.fetch = async () => new Response("", { status: 500 });
  await assert.rejects(() => menu.fetchMenu(), /HTTP 500/);
  console.log("  fetchMenu: API HTTP 오류 OK");

  globalThis.fetch = async () => new Response(JSON.stringify({ error: "점검 중입니다" }), { status: 200 });
  await assert.rejects(() => menu.fetchMenu(), /점검 중입니다/);
  console.log("  fetchMenu: API가 error 필드를 내려주면 그대로 전달 OK");

  globalThis.fetch = async () => new Response(JSON.stringify({ today: { meals: [] } }), { status: 200 });
  await assert.rejects(() => menu.fetchMenu(), /식단 정보가 없습니다/);
  console.log("  fetchMenu: 오늘 끼니가 비어 있으면 예외 OK");
}

async function testFetchMenuPrefersServiceBinding() {
  globalThis.fetch = async () => {
    throw new Error("Service Binding이 주어지면 전역 fetch를 쓰면 안 됩니다 (계정 내 Worker 간 fetch는 404남)");
  };
  let called = false;
  const fakeBinding = {
    fetch: async (url, init) => {
      called = true;
      assert.equal(url.toString(), DAEWON_API_URL);
      assert.equal(init.method, "POST");
      return new Response(
        JSON.stringify({ today: { meals: [{ type: "조식", items: ["쌀밥"] }] } }),
        { status: 200 },
      );
    },
  };
  const text = await menu.fetchMenu(fakeBinding);
  assert.ok(called, "넘겨준 바인딩의 fetch가 호출되어야 함");
  assert.ok(text.includes("쌀밥"));
  console.log("  fetchMenu: Service Binding(Fetcher)이 있으면 그걸 우선 사용 + 전역 fetch 미사용 OK");
}

testKstDateString();
testFormatMealsText();
testFormatMealsTextKeepsOnlyFirstDay();
testMakeMenuEmbed();
await testFetchMenuSuccess();
await testFetchMenuHandlesErrors();
await testFetchMenuPrefersServiceBinding();
console.log("menu-source.ts 전부 통과 ✅");
