/**
 * 고속도로 돌발상황(사고/공사/기타통제/기상통제) 조회.
 *
 * 한국도로공사(EX) Open API(data.ex.co.kr) "돌발정보" 서비스를 씁니다.
 * data.ex.co.kr에서 무료로 API 키를 발급받아 HIGHWAY_API_KEY secret으로
 * 등록해야 동작합니다.
 *
 * ⚠️ 필드 이름은 공개된 문서를 기준으로 최선으로 맞춘 것입니다. 실제 키를
 * 발급받아 연결한 뒤 기존 진단 엔드포인트
 * (`/setup/debug-menu?token=...&url=` + 이 API의 실제 요청 주소를
 * URL 인코딩한 값)로 원본 응답을 확인해 다듬어야 할 수 있습니다 — 식단
 * API(daewon-dispatch)를 처음 연결했을 때와 같은 과정입니다. 응답 형태가
 * 예상과 달라도 parseIncidents()가 조용히 빈 배열을 돌려줄 뿐 죽지는
 * 않습니다.
 */

export const HIGHWAY_API_URL = "https://data.ex.co.kr/openapi/trafficapi/eventInfo";

export interface Incident {
  /** 중복 알림 방지에 쓰는 고유 키. API가 안 주면 나머지 필드를 조합해 만듭니다. */
  key: string;
  message: string;
  roadName?: string;
  kind?: string;
  startName?: string;
  endName?: string;
}

interface RawIncident {
  key?: string | number;
  msg?: string;
  message?: string;
  roadName?: string;
  kind?: string;
  gubun?: string;
  startName?: string;
  endName?: string;
  startDate?: string;
  startTime?: string;
}

function fallbackKey(item: RawIncident): string {
  return [item.roadName, item.startName, item.endName, item.startDate, item.startTime]
    .filter(Boolean)
    .join("|");
}

/** API 응답(list 배열)을 우리 Incident 형태로 정리합니다. 모르는 형태면 빈 배열. */
export function parseIncidents(raw: unknown): Incident[] {
  const list = (raw as { list?: RawIncident[] } | null)?.list;
  if (!Array.isArray(list)) return [];

  const incidents: Incident[] = [];
  for (const item of list) {
    const message = item.msg ?? item.message;
    if (!message) continue;

    const key = String(item.key ?? fallbackKey(item));
    if (!key) continue;

    incidents.push({
      key,
      message,
      roadName: item.roadName,
      kind: item.kind ?? item.gubun,
      startName: item.startName,
      endName: item.endName,
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
  const section = [incident.startName, incident.endName].filter(Boolean).join(" ~ ");

  return {
    title: `🚧 ${titleParts.length > 0 ? titleParts.join(" · ") : "고속도로 돌발상황"}`,
    description: incident.message,
    color: 0xed4245,
    fields: section ? [{ name: "구간", value: section, inline: false }] : undefined,
  };
}
