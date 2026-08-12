/**
 * 고속도로 구간별 소통정보(교통량·속도·정체도) 조회.
 *
 * 한국도로공사(EX) Open API(data.ex.co.kr)의 "구간별 소통정보"
 * (trafficAmountByCongest) 서비스를 씁니다. 처음엔 "돌발정보"(사고/공사/
 * 통제) API를 쓰려 했지만, 실제로 발급받아 확인해 보니 그런 사고/통제
 * 설명이 있는 API가 아니라 도로 구간(VDS 센서)별 속도·교통량·소통등급
 * (grade) 숫자만 주는 API였습니다. 그래서 "돌발상황 알림" 대신 "심한
 * 정체 구간 알림"으로 씁니다 — grade가 정체를 뜻하는 값일 때만 알림
 * 대상으로 고릅니다. 사고/통제 자체는 이 API로는 알 수 없습니다.
 *
 * data.ex.co.kr에서 무료로 API 키를 발급받아 HIGHWAY_API_KEY secret으로
 * 등록해야 동작합니다.
 *
 * ⚠️ grade 값의 정확한 인코딩(숫자 코드 "3"인지 "정체" 같은 텍스트인지)은
 * 아직 실제 응답으로 확인되지 않았습니다. 숫자 "3"과, 텍스트 안에 "정체"가
 * 포함된 경우를 모두 심한 정체로 인식하도록 방어적으로 작성했습니다 —
 * `/setup/debug-menu?token=...&target=traffic` 으로 실제 응답을 보고
 * `isSevereCongestion()`만 다듬으면 됩니다.
 */

export const HIGHWAY_API_URL = "https://data.ex.co.kr/openapi/odtraffic/trafficAmountByCongest";

export interface Incident {
  /** 중복 알림 방지에 쓰는 고유 키(도로+구간+방향 조합 — 시각은 포함하지 않음). */
  key: string;
  message: string;
  roadName?: string;
  kind?: string;
  startName?: string;
  endName?: string;
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

/** grade 인코딩이 아직 불확실해서, 숫자 코드/텍스트 두 가능성을 모두 받아줍니다. */
function isSevereCongestion(grade: string | undefined): boolean {
  if (!grade) return false;
  return grade === "3" || grade.includes("정체");
}

/** API 응답(list 배열)에서 심한 정체 구간만 골라 우리 Incident 형태로 정리합니다. */
export function parseIncidents(raw: unknown): Incident[] {
  const list = (raw as { list?: RawSegment[] } | null)?.list;
  if (!Array.isArray(list)) return [];

  const incidents: Incident[] = [];
  for (const item of list) {
    if (!isSevereCongestion(item.grade)) continue;

    const key = [item.routeNo, item.conzoneId, item.updownTypeCode].filter(Boolean).join("|");
    if (!key) continue;

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

export async function fetchIncidents(
  apiKey: string,
  fetcher: { fetch: typeof fetch } = { fetch },
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
