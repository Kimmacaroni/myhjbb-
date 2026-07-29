import assert from "node:assert/strict";
import * as menu from "./.bundled-menu-source.mjs";

function testKstDateString() {
  // UTC 2026-07-28 15:30 = KST 2026-07-29 00:30 (자정을 넘는 경계 확인)
  const d = new Date("2026-07-28T15:30:00Z");
  assert.equal(menu.kstDateString(d), "2026년 07월 29일");
  console.log("  kstDateString: UTC→KST 자정 경계 변환 + 0패딩 OK");
}

function testFormatMenuText() {
  const raw = "\n  2026년 7월 29일  \n\n중식\n제육볶음\n된장국\n\n석식\n고등어구이\n";
  const text = menu.formatMenuText(raw);
  assert.equal(text.split("─".repeat(20)).length - 1, 2, "구분선이 2번(중식/석식) 들어가야 함");
  assert.ok(text.indexOf("─".repeat(20)) < text.indexOf("중식"));
  assert.ok(!text.includes("  2026")); // 앞뒤 공백 제거됐는지
  console.log("  formatMenuText: 구분선 삽입 + 공백 정리 OK");

  assert.throws(() => menu.formatMenuText(""), /비어 있습니다/);
  assert.throws(() => menu.formatMenuText("   \n  \n"), /비어 있습니다/);
  console.log("  formatMenuText: 빈 내용이면 예외 OK");
}

function testFormatMenuTextDropsSecondDay() {
  // 실제 사이트가 반환한 샘플: 오늘+내일 식단이 구분자 없이 이어붙어 옵니다.
  const raw = [
    "조식열량 : 603Kcal", "쌀밥", "얼큰우거지닭곰탕", "배추김치",
    "중식열량 : 1084Kcal", "쌀밥", "불고기나물비빔밥&고추장", "배추김치", "요구르트",
    "석식열량 : 818Kcal", "쌀밥", "돈육고추잡채", "무우생채", "배추김치",
    // 여기서부터 내일 식단 — 잘려나가야 함
    "조식열량 : 583Kcal", "쌀밥", "장터국", "배추김치",
    "중식열량 : 1020Kcal", "기장밥", "돈육고추장불고기", "배추김치",
    "석식열량 : 857Kcal", "쌀밥", "마파두부", "배추김치",
  ].join("\n");

  const text = menu.formatMenuText(raw);
  assert.ok(text.includes("얼큰우거지닭곰탕"), "오늘 조식은 남아있어야 함");
  assert.ok(text.includes("불고기나물비빔밥"), "오늘 중식은 남아있어야 함");
  assert.ok(text.includes("돈육고추잡채"), "오늘 석식은 남아있어야 함");
  assert.ok(!text.includes("장터국"), "내일 조식은 잘려야 함");
  assert.ok(!text.includes("돈육고추장불고기"), "내일 중식은 잘려야 함");
  assert.ok(!text.includes("마파두부"), "내일 석식은 잘려야 함");
  assert.equal(text.split("─".repeat(20)).length - 1, 2, "오늘 몫만 남아 구분선도 2번이어야 함");

  // 하루치만 오는 정상 케이스는 그대로 다 남아야 함 (오탐 방지)
  const singleDay = ["조식열량 : 500Kcal", "쌀밥", "중식열량 : 900Kcal", "된장국"].join("\n");
  const singleDayResult = menu.formatMenuText(singleDay);
  assert.ok(singleDayResult.includes("500Kcal") && singleDayResult.includes("된장국"));
  assert.equal(singleDayResult.split("\n").length, 5); // 원본 4줄 + 중식 구분선 1줄

  console.log("  formatMenuText: 두 번째 날(내일) 잘라내기 + 하루치만 있을 때 오탐 방지 OK");
}

function testMakeMenuEmbed() {
  const embed = menu.makeMenuEmbed("중식\n제육볶음", new Date("2026-07-29T00:00:00Z"));
  assert.match(embed.title, /식단 브리핑/);
  assert.match(embed.description, /제육볶음/);
  assert.match(embed.description, /\*\*날짜: \d{4}년 \d{2}월 \d{2}일\*\*/);
  assert.equal(embed.color, 15158332);
  console.log("  makeMenuEmbed: 임베드 구조 OK");
}

testKstDateString();
testFormatMenuText();
testFormatMenuTextDropsSecondDay();
testMakeMenuEmbed();
console.log("menu-source.ts (순수 로직) 전부 통과 ✅");
console.log("  ※ fetchMenu()는 HTMLRewriter(Workers 전용)를 쓰므로 Node에서 테스트 불가 — 배포 후 /식단 으로 직접 확인 필요");
