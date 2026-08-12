/**
 * 식단 정보 조회 및 임베드 생성. Python 버전(menu_source.py)의 이식입니다.
 *
 * buspia.co.kr 사이트를 직접 크롤링하던 이전 방식은 사이트 구조가 바뀌며
 * 깨졌습니다. 대신 같은 정보를 이미 정리해서 제공하고 있는 대원여객
 * 배차확인 앱의 Worker API(daewon-dispatch)를 호출합니다 — 소유자 확인 후
 * 재사용을 허락받았습니다. 일반 fetch + JSON이라 Node에서도 그대로
 * 테스트할 수 있습니다 (더는 Workers 전용 HTMLRewriter가 필요 없습니다).
 *
 * ⚠️ 같은 Cloudflare 계정 안의 *.workers.dev Worker끼리는 무한 루프 방지를
 * 위해 일반 fetch()로 서로를 호출할 수 없습니다(HTTP 404, cf-ray 오류 코드
 * 1042). 그래서 fetchMenu()는 Service Binding(Fetcher)을 우선 쓰고, 로컬
 * 테스트나 바인딩이 아직 없는 환경에서는 전역 fetch로 자연스럽게
 * 대체됩니다.
 */

export const DAEWON_API_URL = "https://daewon-dispatch.kcy990830.workers.dev";
export const MENU_HOUR_KST = 6;

export interface Meal {
  type: string; // "조식" | "중식" | "석식"
  items: string[];
  kcal?: number;
}

interface DaewonFoodMenuResponse {
  today?: { date?: string; meals?: Meal[] };
  tomorrow?: { date?: string; meals?: Meal[] };
  error?: string;
}

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

/** API가 내려준 끼니 목록(조식/중식/석식)을 중식/석식 앞에 구분선을 넣어 텍스트로 만듭니다. */
export function formatMealsText(meals: Meal[] | undefined): string {
  if (!meals || meals.length === 0) {
    throw new Error("오늘의 식단 정보가 없습니다.");
  }

  const lines: string[] = [];
  for (const meal of meals) {
    if (meal.type === "중식" || meal.type === "석식") {
      lines.push("─".repeat(20));
    }
    const kcalPart = meal.kcal ? ` (${meal.kcal}Kcal)` : "";
    lines.push(`${meal.type}${kcalPart}`);
    for (const item of meal.items ?? []) {
      lines.push(item);
    }
  }
  return lines.join("\n");
}

export function makeMenuEmbed(menuText: string, now: Date = new Date()) {
  return {
    title: "🏢 명예회장님의 오늘의 식단 브리핑",
    description: `**날짜: ${kstDateString(now)}**\n\n${menuText}`,
    color: 15158332,
    footer: { text: "KD 운송그룹이 가는 곳에 길이 있습니다.\n길이 있는 곳에 KD 운송그룹이 있습니다." },
  };
}

/**
 * daewon-dispatch Worker의 오늘 식단 정보를 받아 텍스트로 정리합니다.
 *
 * @param fetcher Service Binding(env.DAEWON_API) 또는 테스트용 fetch 대체.
 *   생략하면 전역 fetch를 씁니다 — 실제 배포 환경에서는 반드시 Service
 *   Binding을 넘겨야 계정 내 Worker 간 fetch 제한(오류 1042)을 피합니다.
 */
export async function fetchMenu(fetcher: { fetch: typeof fetch } = { fetch }): Promise<string> {
  const response = await fetcher.fetch(DAEWON_API_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action: "foodmenu" }),
  });
  if (!response.ok) {
    throw new Error(`식단 API 응답 오류: HTTP ${response.status}`);
  }

  const data = await response.json<DaewonFoodMenuResponse>();
  if (data.error) {
    throw new Error(data.error);
  }
  return formatMealsText(data.today?.meals);
}
