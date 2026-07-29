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
testMakeMenuEmbed();
console.log("menu-source.ts (순수 로직) 전부 통과 ✅");
console.log("  ※ fetchMenu()는 HTMLRewriter(Workers 전용)를 쓰므로 Node에서 테스트 불가 — 배포 후 /식단 으로 직접 확인 필요");
