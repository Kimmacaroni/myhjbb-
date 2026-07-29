/**
 * 식단표 크롤링 및 임베드 생성. Python 버전(menu_source.py)의 이식입니다.
 *
 * 텍스트 정리(formatMenuText)와 임베드 조립(makeMenuEmbed)은 순수 함수라
 * Node에서 바로 테스트할 수 있습니다. fetchMenu만 Cloudflare의 HTMLRewriter
 * (Workers 런타임 전용 API)를 쓰기 때문에 Node에서는 실행할 수 없습니다 —
 * 배포 후 `/식단` 명령어로 실제 동작을 확인해야 합니다.
 */

export const MENU_URL = "https://www.buspia.co.kr/m/intranet/subpage/my/foodtable.php";
export const MENU_HOUR_KST = 6;

/** 날짜를 "2026년 07월 29일" 형식(KST, 0으로 패딩)으로 만듭니다. */
export function kstDateString(date: Date): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const map = Object.fromEntries(parts.map((p) => [p.type, p.value]));
  return `${map.year}년 ${map.month}월 ${map.day}일`;
}

/** HTML에서 뽑아낸 원본 텍스트를 다듬어 중식/석식 앞에 구분선을 넣습니다. */
export function formatMenuText(rawText: string): string {
  const lines = rawText
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);
  if (lines.length === 0) {
    throw new Error("식단표가 비어 있습니다.");
  }

  const final: string[] = [];
  for (const line of lines) {
    if (line.includes("중식") || line.includes("석식")) {
      final.push("─".repeat(20));
    }
    final.push(line);
  }
  return final.join("\n");
}

export function makeMenuEmbed(menuText: string, now: Date = new Date()) {
  return {
    title: "🏢 명예회장님의 오늘의 식단 브리핑",
    description: `**날짜: ${kstDateString(now)}**\n\n${menuText}`,
    color: 15158332,
    footer: { text: "오늘도 안전 운행하십시오. 대원여객 파이팅!" },
  };
}

async function extractBySelector(response: Response, selector: string): Promise<string> {
  let out = "";
  const rewriter = new HTMLRewriter().on(selector, {
    text(el: { text: string }) {
      out += el.text;
    },
  });
  await rewriter.transform(response).text();
  return out;
}

/** 식단표 페이지를 읽어 텍스트로 정리합니다. (Workers 전용 — HTMLRewriter 사용) */
export async function fetchMenu(): Promise<string> {
  const response = await fetch(MENU_URL, { headers: { "User-Agent": "Mozilla/5.0" } });
  if (!response.ok) {
    throw new Error(`식단표 페이지 응답 오류: HTTP ${response.status}`);
  }

  // Response 본문은 한 번만 읽을 수 있으므로, 두 번째 시도를 위해 미리 복제해 둡니다.
  const clone = response.clone();

  let raw = await extractBySelector(response, "div.content");
  if (!raw.trim()) {
    raw = await extractBySelector(clone, "table");
  }
  if (!raw.trim()) {
    throw new Error("식단표 영역을 찾지 못했습니다. 사이트 구조가 바뀌었을 수 있습니다.");
  }

  return formatMenuText(raw);
}
