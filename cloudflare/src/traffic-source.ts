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
 *
 * 전국 고속도로를 다 알려주면 필요없는 지역 소식까지 너무 많이 와서,
 * 수도권(서울/인천/경기) 구간만 걸러서 알립니다. API 응답에는 지역
 * 구분값이나 좌표가 따로 없고 도로 이름(routeName)과 구간 이름
 * (conzoneName, 예: "금토JC-양재IC")만 있어서 두 단계로 거릅니다:
 *
 * 1) 도로 이름이 수도권을 지나는 노선인지 (CAPITAL_REGION_ROAD_KEYWORDS)
 * 2) 그 도로여도, 실제 발급받은 API 응답으로 확인해 보니 경부선·중부선·
 *    영동선처럼 수도권 밖까지 뻗은 노선은 지방 구간(대전·충북·강원 등)의
 *    정체도 같은 도로 이름으로 섞여서 옵니다 — 그래서 구간 이름에 수도권
 *    밖 지명이 있으면 도로 이름이 맞아도 제외합니다
 *    (NON_CAPITAL_REGION_SEGMENT_KEYWORDS).
 *
 * 이 목록은 실제 API 응답(2026-08-19, HIGHWAY_API_KEY로 조회) 58건을 보고
 * 수도권/비수도권을 직접 구분해서 만들었습니다 — 예를 들어 같은 경부선
 * 응답 안에 "금토JC-양재IC"(수도권, 성남~서초)와 "신탄진IC-회덕JC"(대전)가
 * 함께 있었습니다. 다만 전국 모든 나들목을 다 검증한 목록은 아니라서,
 * 수도권 밖 구간이 새로 나타나면 이 목록에 추가해야 할 수 있습니다.
 */

export const HIGHWAY_API_URL = "https://data.ex.co.kr/openapi/odtraffic/trafficAmountByCongest";

/**
 * 수도권(서울/인천/경기)을 지나는 주요 고속도로 노선명 키워드입니다.
 * routeName이 이 중 하나라도 포함하면 수도권 관련 도로로 봅니다.
 *   경부(경부선), 서해안(서해안선), 영동(영동선), 중부(중부선·중부내륙선),
 *   서울양양(서울양양선), 수도권(수도권제1순환선·수도권제2순환선),
 *   평택시흥(평택시흥선), 경인(경인선·제2경인선), 인천(인천김포선 등),
 *   김포(인천김포선), 봉담동탄(봉담동탄선)
 */
const CAPITAL_REGION_ROAD_KEYWORDS = [
  "경부",
  "서해안",
  "영동",
  "중부",
  "서울양양",
  "수도권",
  "평택시흥",
  "경인",
  "인천",
  "김포",
  "봉담동탄",
];

/**
 * 위 도로들 중에서도 수도권 밖으로 나가는 지점의 나들목/분기점 이름
 * 키워드입니다. 구간 이름(conzoneName)에 이 중 하나라도 있으면, 도로
 * 이름은 수도권 노선이 맞아도 그 구간 자체는 수도권 밖으로 보고
 * 제외합니다.
 */
const NON_CAPITAL_REGION_SEGMENT_KEYWORDS = [
  // 경부선: 천안(충남)부터 수도권 밖 (대전·구미·대구·부산 방향)
  "천안", "목천", "청주", "청원", "옥천", "신탄진", "회덕", "매포",
  "영동IC", "김천", "구미", "칠곡", "대구", "경산", "밀양", "양산", "부산",
  // 중부선: 일죽/이천을 지나 음성·진천·충주부터 수도권 밖
  "삼성Hi", "대소", "진천", "음성", "충주", "괴산", "증평",
  // 영동선: 용인/양지를 지나 원주부터 수도권 밖(강원)
  "문막", "만종", "횡성", "새말", "둔내", "면온", "평창", "진부", "강릉", "대관령",
  // 서해안선: 화성/평택을 지나 당진부터 수도권 밖(충남 이남)
  "당진", "서산", "홍성", "보령", "서천", "군산", "부안", "고창", "무안", "목포",
  // 서울양양선: 가평을 지나 홍천부터 수도권 밖(강원)
  "홍천", "인제", "양양", "속초",
];

/** 도로 이름이 수도권 주요 고속도로에 해당하는지 확인합니다. */
export function isCapitalRegionRoad(roadName: string | undefined): boolean {
  if (!roadName) return false;
  return CAPITAL_REGION_ROAD_KEYWORDS.some((keyword) => roadName.includes(keyword));
}

/** 도로 이름과 구간 이름을 함께 봐서, 실제로 수도권 안의 구간인지 확인합니다. */
export function isCapitalRegionSegment(roadName: string | undefined, segmentName: string | undefined): boolean {
  if (!isCapitalRegionRoad(roadName)) return false;
  if (segmentName && NON_CAPITAL_REGION_SEGMENT_KEYWORDS.some((keyword) => segmentName.includes(keyword))) {
    return false;
  }
  return true;
}

export interface Incident {
  /** 중복 알림 방지에 쓰는 고유 키(도로+구간+방향 조합 — 시각/센서는 포함하지 않음). */
  key: string;
  message: string;
  roadName?: string;
  kind?: string;
  startName?: string;
  /** 도로명을 뺀 구간 설명("{구간명} {방향} 정체 중 (...)") — 도로별로 묶어 보여줄 때 씁니다. */
  segmentText: string;
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
    const segment = [item.conzoneName, direction].filter(Boolean).join(" ");
    const speedText = item.speed ? `평균 속도 ${item.speed}km/h` : "정체 심함";

    incidents.push({
      key,
      message: `${location || "구간 정보 없음"} 정체 중 (${speedText})`,
      roadName: item.routeName,
      kind: "정체",
      startName: item.conzoneName,
      segmentText: `${segment || "구간 정보 없음"} 정체 중 (${speedText})`,
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
  return parseIncidents(data).filter((incident) => isCapitalRegionSegment(incident.roadName, incident.startName));
}

/**
 * /교통정보 명령어에서 한 메시지(텍스트) 안에 고속도로별로 묶어 보여줄 때 씁니다.
 * 예:
 *   🚧 영동고속도로
 *   - 신갈분기점 기점 방향 정체 중 (평균 속도 12km/h)
 *   - 여주휴게소 종점 방향 정체 중 (평균 속도 18km/h)
 */
export function formatIncidentLinesByRoad(incidents: Incident[]): string[] {
  const groups = new Map<string, Incident[]>();
  for (const incident of incidents) {
    const road = incident.roadName || "도로 정보 없음";
    const group = groups.get(road);
    if (group) group.push(incident);
    else groups.set(road, [incident]);
  }

  const lines: string[] = [];
  for (const [road, group] of groups) {
    lines.push(`🚧 **${road}**`);
    for (const incident of group) {
      lines.push(`- ${incident.segmentText}`);
    }
  }
  return lines;
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

/**
 * 자동으로 보내는 알림(scheduled.ts)에서, 같은 고속도로의 구간들을
 * 임베드 하나로 묶어 보여줄 때 씁니다 — 도로마다 임베드가 따로따로
 * 오지 않도록.
 */
export function makeRoadEmbeds(incidents: Incident[]) {
  const groups = new Map<string, Incident[]>();
  for (const incident of incidents) {
    const road = incident.roadName || "도로 정보 없음";
    const group = groups.get(road);
    if (group) group.push(incident);
    else groups.set(road, [incident]);
  }

  return [...groups.entries()].map(([road, group]) => ({
    title: `🚧 ${road}`,
    description: group.map((incident) => `- ${incident.segmentText}`).join("\n"),
    color: 0xed4245,
  }));
}
