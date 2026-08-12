/**
 * 고속도로 정체 구간(구간별 소통정보) 조회.
 *
 * 한국도로공사(EX) Open API(data.ex.co.kr)의 "구간별 소통정보"
 * (trafficAmountByCongest) 서비스를 씁니다. 처음엔 "돌발정보"(사고/공사/
 * 통제) API를 쓰려 했지만, 실제로 발급받아 확인해 보니 그런 사고/통제
 * 설명이 있는 API가 아니었습니다.
 *
 * 실제 응답을 두 번 받아 확인한 결과, 이 API는 이름(...ByCongest) 그대로
 * **이미 정체로 분류된 구간만** 돌려주는 것으로 보입니다 — 두 응답 모두
 * 모든 항목의 grade가 "3"으로 동일했습니다. 그래서 grade로 다시 거르지
 * 않고, 응답에 있는 구간을 그대로 알림 대상으로 씁니다. 대신 같은
 * 구간(conzone)에 VDS 센서가 여러 개 있어 항목이 중복으로 오므로, 구간당
 * 속도가 가장 낮은(가장 정체가 심한) 값 하나만 남깁니다.
 *
 * data.ex.co.kr에서 무료로 API 키를 발급받아 HIGHWAY_API_KEY secret으로
 * 등록해야 동작합니다.
 */

export const HIGHWAY_API_URL = "https://data.ex.co.kr/openapi/odtraffic/trafficAmountByCongest";

export interface Incident {
  /** 중복 알림 방지에 쓰는 고유 키(도로+구간+방향 조합 — 시각/센서는 포함하지 않음). */
  key: string;
  message: string;
  roadName?: string;
  kind?: string;
  startName?: string;
}

interface RawSegment {
  stdDate?: string;
  stdHour?: string;
  vdsId?: string;
  trafficAmout?: string;
  speed?: string;
  shareRatio?: string;
  timeAvg?: string;
  grade?: string;
  routeNo?: string;
  routeName?: string;
  updownTypeCode?: string; // S: 기점 방향, E: 종점 방향
  conzoneId?: string;
  conzoneName?: string;
}

const DIRECTION_LABEL: Record<string, string> = { S: "기점 방향", E: "종점 방향" };

function segmentKey(item: RawSegment): string {
  return [item.routeNo, item.conzoneId, item.updownTypeCode].filter(Boolean).join("|");
}

function toSpeed(speed: string | undefined): number {
  const n = Number(speed);
  return Number.isFinite(n) ? n : Infinity;
}

/** API 응답(list 배열)을 구간(conzone) 단위로 합쳐 우리 Incident 형태로 정리합니다. */
export function parseIncidents(raw: unknown): Incident[] {
  const list = (raw as { list?: RawSegment[] } | null)?.list;
  if (!Array.isArray(list)) return [];

  // 같은 구간에 VDS 센서가 여러 개 잡히면, 그중 속도가 가장 낮은(가장 막히는) 값만 남깁니다.
  const worstBySegment = new Map<string, RawSegment>();
  for (const item of list) {
    const key = segmentKey(item);
    if (!key) continue;
    const existing = worstBySegment.get(key);
    if (!existing || toSpeed(item.speed) < toSpeed(existing.speed)) {
      worstBySegment.set(key, item);
    }
  }

  const incidents: Incident[] = [];
  for (const [key, item] of worstBySegment) {
    const direction = item.updownTypeCode ? DIRECTION_LABEL[item.updownTypeCode] ?? item.updownTypeCode : undefined;
    const location = [item.routeName, item.conzoneName, direction].filter(Boolean).join(" ");
    const speedText = item.speed ? `평균 속도 ${item.speed}km/h` : "정체 심함";

    incidents.push({
      key,
      message: `${location || "구간 정보 없음"} 정체 중 (${speedText})`,
      roadName: item.routeName,
      kind: "정체",
      startName: item.conzoneName,
    });
  }
  return incidents;
}

/**
 * @param fetcher 테스트용 fetch 대체. 생략하면 전역 fetch를 씁니다.
 *   기본값을 `fetch.bind(globalThis)`로 감싸는 이유: Workers 런타임에서
 *   `{ fetch }`처럼 객체에 담아 `obj.fetch(...)`로 부르면 "Illegal
 *   invocation" 오류가 납니다 — bind로 감싸야 안전합니다. (Node 테스트
 *   환경에서는 이 제약이 없어서 테스트로는 못 잡고 실제 배포 후에야
 *   드러났습니다.)
 */
export async function fetchIncidents(
  apiKey: string,
  fetcher: { fetch: typeof fetch } = { fetch: fetch.bind(globalThis) },
): Promise<Incident[]> {
  const url = new URL(HIGHWAY_API_URL);
  url.searchParams.set("key", apiKey);
  url.searchParams.set("type", "json");

  const response = await fetcher.fetch(url.toString(), { headers: { "User-Agent": "Mozilla/5.0" } });
  if (!response.ok) {
    throw new Error(`교통정보 API 응답 오류: HTTP ${response.status}`);
  }
  const data = await response.json();
  return parseIncidents(data);
}

export function makeIncidentEmbed(incident: Incident) {
  const titleParts = [incident.roadName, incident.kind].filter(Boolean);

  return {
    title: `🚧 ${titleParts.length > 0 ? titleParts.join(" · ") : "고속도로 정체"}`,
    description: incident.message,
    color: 0xed4245,
    fields: incident.startName ? [{ name: "구간", value: incident.startName, inline: false }] : undefined,
  };
}
